"""PolicyRetriever — L2 Context: Qdrant vector search over the refund policy.

Uses fastembed BAAI/bge-small-en-v1.5 (384-dim) for embedding, matching the
dimension used by scripts/seed_qdrant.py. No Azure OpenAI embeddings are used
here — fastembed is deterministic, local, and consumes no quota.

The module-level ``_retriever_singleton`` is assigned by ``get_retriever()``
the first time it is called. Tests can reset it to ``None`` between test cases.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastembed import TextEmbedding  # type: ignore[import]
from qdrant_client import QdrantClient  # type: ignore[import]

from app.config import settings
from app.domain.models import LayerName, PolicyClause
from app.observability import get_emitter, get_logger

logger = get_logger(__name__)

# mypy: no-strict-optional — TextEmbedding lacks stubs; ignore_missing_imports covers it
_retriever_singleton: "PolicyRetriever | None" = None


class PolicyRetriever:
    """Wraps fastembed + Qdrant to return list[PolicyClause] for a query string.

    Lifecycle is managed by ``get_retriever()``. Do not instantiate directly in
    production code — call ``get_retriever()`` instead so the singleton is honoured.
    """

    def __init__(self) -> None:
        self._embed_model: Any = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self._client: Any = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )
        self._collection = settings.QDRANT_COLLECTION_POLICY
        self._verify_collection()

    # ------------------------------------------------------------------
    # Initialisation helper
    # ------------------------------------------------------------------

    def _verify_collection(self) -> None:
        """Raise RuntimeError if the policy collection is missing in Qdrant."""
        try:
            self._client.get_collection(self._collection)
        except Exception:
            raise RuntimeError("Run `make seed` first")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search(self, query: str, top_k: int = 5) -> list[PolicyClause]:
        """Embed *query*, search Qdrant, return top-k PolicyClause objects.

        The call is async; the underlying Qdrant client is synchronous so the
        blocking call is delegated to ``asyncio.to_thread``.
        """
        emitter = get_emitter()
        t0 = time.monotonic()

        # Embed in executor to avoid blocking the event loop
        def _embed() -> list[float]:
            vecs = list(self._embed_model.embed([query]))
            return list(vecs[0])

        vector = await asyncio.to_thread(_embed)

        # Qdrant search in executor
        def _search() -> list[Any]:
            return self._client.search(
                collection_name=self._collection,
                query_vector=vector,
                limit=top_k,
            )

        raw_results = await asyncio.to_thread(_search)
        latency_ms = (time.monotonic() - t0) * 1000.0

        clauses: list[PolicyClause] = []
        for hit in raw_results:
            payload = hit.payload or {}
            clauses.append(
                PolicyClause(
                    clause_id=payload.get("clause_id", "POLICY-UNK"),
                    text=payload.get("text", ""),
                    relevance_score=float(hit.score),
                )
            )

        emitter.emit(
            conversation_id="__retriever__",
            layer=LayerName.CONTEXT,
            event_type="retrieval_performed",
            payload={
                "query": query,
                "top_k": top_k,
                "latency_ms": latency_ms,
                "returned_clauses": len(clauses),
            },
        )

        logger.debug(
            "retrieval_performed",
            extra={"query": query, "top_k": top_k, "returned_clauses": len(clauses)},
        )

        return clauses


def get_retriever() -> PolicyRetriever:
    """Return the process-global PolicyRetriever singleton.

    On the first call the retriever verifies that the Qdrant collection exists.
    Raises ``RuntimeError("Run `make seed` first")`` if the collection is absent.
    """
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = PolicyRetriever()
    return _retriever_singleton
