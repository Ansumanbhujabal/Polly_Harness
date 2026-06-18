"""L6 Graph nodes package.

Each node is a pure async function (or sync for intake) that:
1. Opens a node_scope context (emits node_entered / node_exited).
2. Reads from the state dict.
3. Returns a dict of state updates.

Nodes that require the injectable LLM accept it as a second argument.
The graph builder wires LLM injection via functools.partial.
"""

from app.graph.nodes.await_human_approval import await_human_approval_node
from app.graph.nodes.classify_intent import classify_intent_node
from app.graph.nodes.compute_decision import compute_decision_node
from app.graph.nodes.eligibility_check import eligibility_check_node
from app.graph.nodes.escalate import escalate_node
from app.graph.nodes.fraud_check import fraud_check_node
from app.graph.nodes.identify_customer import identify_customer_node
from app.graph.nodes.intake import intake_node
from app.graph.nodes.issue_refund_node import issue_refund_node
from app.graph.nodes.respond import respond_node
from app.graph.nodes.retrieve_policy import retrieve_policy_node
from app.graph.nodes.verification import verification_node

__all__ = [
    "intake_node",
    "classify_intent_node",
    "identify_customer_node",
    "retrieve_policy_node",
    "eligibility_check_node",
    "fraud_check_node",
    "compute_decision_node",
    "verification_node",
    "issue_refund_node",
    "await_human_approval_node",
    "escalate_node",
    "respond_node",
]
