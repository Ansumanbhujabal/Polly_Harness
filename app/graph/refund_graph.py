"""L6 Orchestration — RefundGraph builder and public facade.

`build_graph(llm=...)` compiles the LangGraph StateGraph with AsyncSqliteSaver
checkpointer. Injectable `llm` parameter allows tests to pass a stub without
any real Azure OpenAI calls.

Public API:
    graph = await build_graph()          # production (lazy Azure OpenAI)
    graph = await build_graph(llm=stub)  # test (deterministic stub)

    result = await graph.ainvoke(state, config)
    result = await graph.ainvoke(Command(resume="approved"), config)
"""

from __future__ import annotations

import functools
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.domain.models import AgentState
from app.graph.edges import (
    route_after_classify_intent,
    route_after_compute_decision,
    route_after_human_approval,
    route_after_identify_customer,
    route_after_verification,
)
from app.graph.nodes import (
    await_human_approval_node,
    classify_intent_node,
    compute_decision_node,
    eligibility_check_node,
    escalate_node,
    fraud_check_node,
    identify_customer_node,
    intake_node,
    issue_refund_node,
    respond_node,
    retrieve_policy_node,
    verification_node,
)


class RefundGraph:
    """Thin wrapper around a compiled LangGraph CompiledStateGraph.

    Methods:
        ainvoke(state_or_command, config) → dict  — run one turn
    """

    def __init__(self, compiled_graph: Any) -> None:
        self._graph = compiled_graph

    async def ainvoke(
        self,
        state_or_command: AgentState | Command | dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the graph for one turn or resume a suspended thread."""
        return await self._graph.ainvoke(state_or_command, config)

    async def aresume(
        self,
        config: dict[str, Any],
        approval: str,
    ) -> dict[str, Any]:
        """Resume a suspended graph with an approval resolution."""
        return await self._graph.ainvoke(Command(resume=approval), config)


def _prepare_approval_node(state: AgentState) -> dict[str, Any]:
    """Internal node: sets awaiting_human_approval=True before the interrupt fires.

    This node runs immediately before await_human_approval_node so that
    the checkpointed state reflects the awaiting flag even when ainvoke()
    returns early due to interrupt(). Also populates response_text with an
    empathetic interim acknowledgement so the customer-facing output isn't
    empty when the graph pauses.
    """
    candidate = state.candidate_decision
    amount = candidate.amount_usd if candidate else 0.0
    response = (
        "I want to make sure this gets the careful look it deserves. "
        f"Your refund request for ${amount:.2f} is above the amount I can approve directly, "
        "so I'm routing it to a senior agent for review. "
        "They'll follow up within 1 business day — if it's urgent, you can reply here and we'll prioritise it."
    )
    return {
        "awaiting_human_approval": True,
        "response_text": response,
    }


def _build_llm() -> BaseLanguageModel:
    """Build the default Azure OpenAI LLM lazily at runtime."""
    from langchain_openai import AzureChatOpenAI  # type: ignore[import]

    from app.config import settings

    return AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_CHAT,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,  # type: ignore[arg-type]
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=0.0,
        max_tokens=512,
    )


async def build_graph(
    llm: BaseLanguageModel | None = None,
) -> RefundGraph:
    """Compile and return the RefundGraph.

    Args:
        llm: Injectable LLM. If None, builds a lazy Azure OpenAI client at
             the first node call that needs it (production path). Tests pass
             a stub to avoid any real API calls.

    Returns:
        RefundGraph wrapping the compiled StateGraph with AsyncSqliteSaver.
    """
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from app.config import settings

    # Resolve LLM: use stub if provided, otherwise lazy production client
    resolved_llm: BaseLanguageModel
    if llm is not None:
        resolved_llm = llm
    else:
        resolved_llm = _build_llm()

    # Build the StateGraph
    builder = StateGraph(AgentState)

    # --- Node registration ---

    # Nodes that DON'T need LLM
    builder.add_node("intake", intake_node)
    builder.add_node("identify_customer", identify_customer_node)
    builder.add_node("retrieve_policy", retrieve_policy_node)
    builder.add_node("eligibility_check", eligibility_check_node)
    builder.add_node("verification", verification_node)
    builder.add_node("issue_refund_node", issue_refund_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("respond", respond_node)

    # Internal pre-approval node: sets awaiting_human_approval=True before interrupt
    builder.add_node("_prepare_approval", _prepare_approval_node)

    # Nodes that need LLM injection via partial
    builder.add_node(
        "classify_intent",
        functools.partial(classify_intent_node, llm=resolved_llm),
    )
    builder.add_node(
        "fraud_check",
        functools.partial(fraud_check_node, llm=resolved_llm),
    )
    builder.add_node(
        "compute_decision",
        compute_decision_node,
    )
    builder.add_node(
        "await_human_approval",
        await_human_approval_node,
    )

    # --- Edge wiring ---

    # Entry: START → intake → classify_intent
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "classify_intent")

    # classify_intent → identify_customer | respond | escalate
    # (off_topic/inquiry short-circuit to respond; injection_attempt/complaint escalate)
    builder.add_conditional_edges(
        "classify_intent",
        route_after_classify_intent,
        {
            "identify_customer": "identify_customer",
            "respond": "respond",
            "escalate": "escalate",
        },
    )

    # identify_customer → retrieve_policy | escalate  (identity mismatch)
    builder.add_conditional_edges(
        "identify_customer",
        route_after_identify_customer,
        {"retrieve_policy": "retrieve_policy", "escalate": "escalate"},
    )

    # retrieve_policy → eligibility_check → fraud_check → compute_decision
    builder.add_edge("retrieve_policy", "eligibility_check")
    builder.add_edge("eligibility_check", "fraud_check")
    builder.add_edge("fraud_check", "compute_decision")

    # compute_decision → verification | escalate  (fraud / missing data skip verification)
    builder.add_conditional_edges(
        "compute_decision",
        route_after_compute_decision,
        {"verification": "verification", "escalate": "escalate"},
    )

    # verification → issue_refund_node | _prepare_approval | escalate
    builder.add_conditional_edges(
        "verification",
        route_after_verification,
        {
            "issue_refund_node": "issue_refund_node",
            "await_human_approval": "_prepare_approval",  # go through prepare first
            "escalate": "escalate",
        },
    )

    # _prepare_approval → await_human_approval (sets flag then suspends)
    builder.add_edge("_prepare_approval", "await_human_approval")

    # await_human_approval → issue_refund_node | escalate  (after resume)
    builder.add_conditional_edges(
        "await_human_approval",
        route_after_human_approval,
        {"issue_refund_node": "issue_refund_node", "escalate": "escalate"},
    )

    # issue_refund_node → respond
    builder.add_edge("issue_refund_node", "respond")

    # escalate → respond
    builder.add_edge("escalate", "respond")

    # respond → END
    builder.add_edge("respond", END)

    # --- Compile with AsyncSqliteSaver ---
    # Use aiosqlite directly so we can hold the connection open across the graph's lifetime.
    # AsyncSqliteSaver.from_conn_string is an async context manager, not a one-shot coroutine,
    # so we open the aiosqlite connection directly and pass it to the constructor.
    import os

    import aiosqlite  # type: ignore[import]

    db_path_str = str(settings.sqlite_full_path)
    os.makedirs(os.path.dirname(db_path_str), exist_ok=True)

    conn = await aiosqlite.connect(db_path_str)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()

    compiled = builder.compile(checkpointer=checkpointer)
    return RefundGraph(compiled)
