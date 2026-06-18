"""compactor — L2 Context: tiktoken-based message compaction with LLM summarisation.

Keeps the conversation message list within a safe token budget. Uses the
``cl100k_base`` encoding (used by gpt-4 / gpt-4o) to count tokens.

Algorithm (when count > max_tokens)
------------------------------------
1. Separate the system message from all other messages.
2. Keep the last 3 non-system messages verbatim (the "tail").
3. Summarise all remaining non-system messages (the "middle") via an LLM call.
4. Reassemble: [system_msg] + [summary_msg] + tail (system omitted if absent).
5. Emit ``compaction_triggered`` with pre/post token counts.

The ``_call_llm_summarize`` function is a module-level callable so tests can
patch it easily with ``mocker.patch("app.context.compactor._call_llm_summarize")``.

The compactor is synchronous. LangGraph nodes that call it from an async context
are responsible for wrapping it in ``asyncio.to_thread`` if needed.
"""

from __future__ import annotations

from typing import Any

import tiktoken

from app.config import settings
from app.domain.models import LayerName
from app.observability import get_emitter, get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_encoding() -> tiktoken.Encoding:
    """Return the cl100k_base tiktoken encoding (gpt-4 / gpt-4o compatible)."""
    return tiktoken.get_encoding("cl100k_base")


def _count_tokens(messages: list[dict[str, Any]]) -> int:
    """Count total tokens across all messages using cl100k_base.

    Uses 4 tokens overhead per message (role + separators) matching OpenAI's
    official counting guidance.
    """
    enc = _get_encoding()
    total = 0
    for msg in messages:
        # Per OpenAI cookbook: 4 tokens per message for role/format overhead
        total += 4
        content = msg.get("content", "") or ""
        total += len(enc.encode(str(content)))
    return total


def _call_llm_summarize(middle: list[dict[str, Any]]) -> str:
    """Call the Azure OpenAI chat model to summarise *middle* messages.

    This function is extracted so tests can patch it without touching the real
    Azure endpoint.  Returns the summary string.
    """
    from openai import AzureOpenAI  # type: ignore[import]

    client = AzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    # Format middle into a readable transcript for the summariser
    transcript_parts: list[str] = []
    for m in middle:
        role = m.get("role", "unknown")
        content = m.get("content", "")
        transcript_parts.append(f"{role.upper()}: {content}")
    transcript = "\n".join(transcript_parts)

    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT_CHAT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a conversation summariser. "
                    "Produce a concise one-paragraph summary of the conversation excerpt below, "
                    "preserving key facts, decisions, and unresolved issues."
                ),
            },
            {
                "role": "user",
                "content": transcript,
            },
        ],
        max_tokens=300,
        temperature=0.0,
    )
    return response.choices[0].message.content or "[summary unavailable]"


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def compact_messages(
    messages: list[dict[str, Any]],
    max_tokens: int = settings.COMPACTION_TOKEN_THRESHOLD,
) -> list[dict[str, Any]]:
    """Trim *messages* to stay within *max_tokens*.

    If the total token count is already ≤ max_tokens, returns the original
    list object unchanged (identity preserved, no copy, no LLM call).

    Parameters
    ----------
    messages:
        OpenAI-format chat messages (list of dicts with at minimum ``"role"``).
    max_tokens:
        Token budget. Defaults to ``settings.COMPACTION_TOKEN_THRESHOLD``.

    Returns
    -------
    The original list if already compact, otherwise a new compacted list.
    """
    pre_tokens = _count_tokens(messages)

    if pre_tokens <= max_tokens:
        return messages

    emitter = get_emitter()

    # Separate system message (at most one)
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    system_msg: dict[str, Any] | None = system_msgs[0] if system_msgs else None

    # Tail: last 3 non-system messages always survive verbatim
    tail = non_system[-3:] if len(non_system) >= 3 else non_system[:]
    middle = non_system[: len(non_system) - len(tail)]

    # Summarise the middle section
    if middle:
        summary_text = _call_llm_summarize(middle)
    else:
        summary_text = "[No prior context to summarise.]"

    summary_msg: dict[str, Any] = {
        "role": "assistant",
        "content": summary_text,
    }

    # Reassemble
    compacted: list[dict[str, Any]] = []
    if system_msg is not None:
        compacted.append(system_msg)
    compacted.append(summary_msg)
    compacted.extend(tail)

    post_tokens = _count_tokens(compacted)

    emitter.emit(
        conversation_id="__compactor__",
        layer=LayerName.CONTEXT,
        event_type="compaction_triggered",
        payload={
            "pre_tokens": pre_tokens,
            "post_tokens": post_tokens,
        },
    )

    logger.debug(
        "compaction_triggered",
        extra={"pre_tokens": pre_tokens, "post_tokens": post_tokens},
    )

    return compacted
