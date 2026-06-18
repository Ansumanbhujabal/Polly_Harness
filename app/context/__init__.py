"""L2 — Context Delivery & Management.

Public surface (exactly three symbols):

    from app.context import get_retriever, build_customer_context, compact_messages

- ``get_retriever()``          → PolicyRetriever singleton (lazy, Qdrant-backed)
- ``build_customer_context()`` → PII-redacted dict for prompt injection
- ``compact_messages()``       → tiktoken-aware message trimmer with LLM summarisation
"""

from app.context.compactor import compact_messages
from app.context.customer_context_builder import build_customer_context
from app.context.retriever import get_retriever

__all__ = [
    "get_retriever",
    "build_customer_context",
    "compact_messages",
]
