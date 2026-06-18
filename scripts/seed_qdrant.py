"""Seed the Qdrant policy collection from refund_policy_v1.md.

Chunking strategy
-----------------
Each inline **POLICY-NNN** clause becomes one chunk.  The regex
``r'\\*\\*POLICY-(\\d{3})\\*\\*'`` matches every bolded clause id in the
markdown source.  The chunk body runs from the POLICY-NNN marker up to
(but not including) the next POLICY-NNN marker or end-of-file.

Metadata per point
------------------
  clause_id     : "POLICY-001"  (used as the deterministic point id)
  section_title : The ``## Section N — …`` heading that contains the clause,
                  or "Preamble" for any text before the first heading.
  text          : The raw chunk text.

Embedding
---------
  fastembed ``BAAI/bge-small-en-v1.5`` → 384-dimensional vectors.

Idempotency
-----------
  Points are upserted (not inserted) using the clause_id as a stable UUID5
  namespace so re-runs produce the same ids without querying first.

CLI
---
  python scripts/seed_qdrant.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

CLAUSE_RE = re.compile(r"\*\*POLICY-(\d{3})\*\*")
SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Namespace for deterministic UUID5 ids (arbitrary but fixed)
_NS = uuid.UUID("7f3e9c2a-1b4d-4f8e-9c7a-2d5b6e8f1a3c")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384  # bge-small-en-v1.5 output dim


# ──────────────────────────────────────────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────────────────────────────────────────


def _section_title_at(pos: int, text: str) -> str:
    """Return the last ## heading that starts before *pos*, or 'Preamble'."""
    title = "Preamble"
    for m in SECTION_RE.finditer(text):
        if m.start() <= pos:
            title = m.group(1).strip()
        else:
            break
    return title


def chunk_policy(text: str) -> list[dict[str, str]]:
    """Split *text* into per-clause chunks.

    Returns a list of dicts:
      {"clause_id": "POLICY-NNN", "section_title": "...", "text": "..."}
    """
    matches = list(CLAUSE_RE.finditer(text))
    chunks: list[dict[str, str]] = []

    for i, m in enumerate(matches):
        clause_id = f"POLICY-{m.group(1)}"
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk_text = text[start:end].strip()
        section_title = _section_title_at(start, text)
        chunks.append(
            {
                "clause_id": clause_id,
                "section_title": section_title,
                "text": chunk_text,
            }
        )

    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# Embedding
# ──────────────────────────────────────────────────────────────────────────────


def _embed_chunks(chunks: list[dict[str, str]]) -> list[list[float]]:
    """Return one embedding vector per chunk using fastembed."""
    from fastembed import TextEmbedding  # type: ignore[import]

    model = TextEmbedding(model_name=EMBED_MODEL)
    texts = [c["text"] for c in chunks]
    return [list(vec) for vec in model.embed(texts)]


# ──────────────────────────────────────────────────────────────────────────────
# Qdrant client factory (separated so tests can patch it)
# ──────────────────────────────────────────────────────────────────────────────


def _build_client():
    """Return a QdrantClient connected to settings.QDRANT_URL."""
    from qdrant_client import QdrantClient  # type: ignore[import]

    from app.config import settings

    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)


# ──────────────────────────────────────────────────────────────────────────────
# Collection bootstrap
# ──────────────────────────────────────────────────────────────────────────────


def _ensure_collection(client: Any, collection_name: str) -> None:
    """Create the collection if it does not already exist."""
    from qdrant_client.models import Distance, VectorParams  # type: ignore[import]

    try:
        client.get_collection(collection_name)
        # Collection exists — nothing to do
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Upsert
# ──────────────────────────────────────────────────────────────────────────────


def _clause_id_to_uuid(clause_id: str) -> str:
    """Deterministic UUID5 keyed on clause_id."""
    return str(uuid.uuid5(_NS, clause_id))


def _build_points(chunks: list[dict[str, str]], vectors: list[list[float]]) -> list[Any]:
    """Build qdrant PointStruct objects."""
    from qdrant_client.models import PointStruct  # type: ignore[import]

    points = []
    for chunk, vec in zip(chunks, vectors):
        points.append(
            PointStruct(
                id=_clause_id_to_uuid(chunk["clause_id"]),
                vector=vec,
                payload={
                    "clause_id": chunk["clause_id"],
                    "section_title": chunk["section_title"],
                    "text": chunk["text"],
                },
            )
        )
    return points


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────


def seed(
    policy_path: Path | None = None,
    collection_name: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    """Chunk, embed, and upsert the policy document.

    Parameters
    ----------
    policy_path:
        Path to the policy markdown. Defaults to ``settings.POLICY_DOC_PATH``.
    collection_name:
        Qdrant collection. Defaults to ``settings.QDRANT_COLLECTION_POLICY``.
    dry_run:
        If True, skip embedding and Qdrant; just return chunks.

    Returns
    -------
    list of chunk dicts (useful for inspection / dry-run output).
    """
    from app.config import settings

    policy_path = policy_path or settings.POLICY_DOC_PATH
    collection_name = collection_name or settings.QDRANT_COLLECTION_POLICY

    text = Path(policy_path).read_text(encoding="utf-8")
    chunks = chunk_policy(text)

    print(f"[seed_qdrant] {len(chunks)} policy chunks extracted from {policy_path}")

    if dry_run:
        for c in chunks:
            print(f"  DRY-RUN  {c['clause_id']}  ({c['section_title']})  {len(c['text'])} chars")
        return chunks

    # Embed
    vectors = _embed_chunks(chunks)

    # Qdrant
    client = _build_client()
    _ensure_collection(client, collection_name)
    points = _build_points(chunks, vectors)
    client.upsert(collection_name=collection_name, points=points)

    print(f"[seed_qdrant] Upserted {len(points)} points into '{collection_name}'.")
    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Seed Qdrant with refund policy chunks.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print chunks without embedding or upserting.",
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        default=None,
        help="Override policy doc path.",
    )
    args = parser.parse_args()
    seed(policy_path=args.policy_path, dry_run=args.dry_run)


if __name__ == "__main__":
    _cli()
