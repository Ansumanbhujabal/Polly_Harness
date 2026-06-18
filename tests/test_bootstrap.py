"""Bootstrap tests — seed_qdrant + langfuse_bootstrap.

TDD: these tests are written first. RED before GREEN.

Test 1: test_seed_qdrant_chunks_policy_by_clause_id
    Mock Qdrant client; assert chunks carry clause_id metadata for each POLICY-NNN section.

Test 2: test_seed_qdrant_idempotent_on_rerun
    Call seed twice; assert the set of upserted point ids is identical both times.

Test 3: test_langfuse_bootstrap_noop_when_module_missing
    Monkeypatch import to raise ImportError; assert exits 0 with the documented log line.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch, call

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "data" / "policy" / "refund_policy_v1.md"

POLICY_CLAUSE_RE = re.compile(r"^\*\*POLICY-(\d{3})\*\*", re.MULTILINE)


def _expected_clause_ids(policy_text: str) -> list[str]:
    """Return all POLICY-NNN ids found in the policy doc (order-preserving, deduped)."""
    seen: list[str] = []
    for m in POLICY_CLAUSE_RE.finditer(policy_text):
        cid = f"POLICY-{m.group(1)}"
        if cid not in seen:
            seen.append(cid)
    return seen


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def policy_text() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def mock_qdrant_client():
    """A fully mocked QdrantClient (collection management + upsert)."""
    client = MagicMock()
    # get_collection raises an exception to simulate "collection not yet created"
    client.get_collection.side_effect = Exception("collection not found")
    return client


@pytest.fixture()
def seed_module():
    """Import scripts.seed_qdrant fresh (bypasses cached module state)."""
    if "scripts.seed_qdrant" in sys.modules:
        del sys.modules["scripts.seed_qdrant"]
    import scripts.seed_qdrant as mod
    return mod


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 — chunks carry clause_id metadata
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_seed_qdrant_chunks_policy_by_clause_id(
    policy_text: str,
    mock_qdrant_client: MagicMock,
    seed_module,
):
    """Each POLICY-NNN section becomes exactly one chunk with matching clause_id metadata."""
    expected_ids = _expected_clause_ids(policy_text)
    assert expected_ids, "Policy doc must contain POLICY-NNN clauses"

    with (
        patch.object(seed_module, "_build_client", return_value=mock_qdrant_client),
        patch.object(seed_module, "_embed_chunks", side_effect=lambda chunks: [[0.0] * 384 for _ in chunks]),
    ):
        seed_module.seed(policy_path=POLICY_PATH, dry_run=False)

    # Collect all upserted payloads
    assert mock_qdrant_client.upsert.called, "upsert must be called at least once"
    upserted_clause_ids: list[str] = []
    for c in mock_qdrant_client.upsert.call_args_list:
        points = c.kwargs.get("points") or c.args[1]
        for p in points:
            payload = p.payload if hasattr(p, "payload") else p.get("payload", {})
            cid = payload.get("clause_id")
            assert cid is not None, f"Point missing clause_id: {p}"
            upserted_clause_ids.append(cid)

    assert sorted(upserted_clause_ids) == sorted(expected_ids), (
        f"Upserted clause_ids {sorted(upserted_clause_ids)} != expected {sorted(expected_ids)}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 — idempotent on re-run
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_seed_qdrant_idempotent_on_rerun(
    policy_text: str,
    mock_qdrant_client: MagicMock,
    seed_module,
):
    """Calling seed() twice produces identical point-id sets — no duplicates, no drift."""
    # On second call, simulate collection already exists (get_collection returns normally)
    mock_qdrant_client.get_collection.side_effect = [Exception("not found"), MagicMock()]

    def _fake_embed(chunks):
        return [[0.0] * 384 for _ in chunks]

    ids_per_run: list[set[str]] = []

    with (
        patch.object(seed_module, "_build_client", return_value=mock_qdrant_client),
        patch.object(seed_module, "_embed_chunks", side_effect=_fake_embed),
    ):
        for _ in range(2):
            mock_qdrant_client.upsert.reset_mock()
            seed_module.seed(policy_path=POLICY_PATH, dry_run=False)
            run_ids: set[str] = set()
            for c in mock_qdrant_client.upsert.call_args_list:
                points = c.kwargs.get("points") or c.args[1]
                for p in points:
                    pid = p.id if hasattr(p, "id") else p.get("id")
                    run_ids.add(str(pid))
            ids_per_run.append(run_ids)

    assert ids_per_run[0] == ids_per_run[1], (
        f"Point ids differed across runs:\nrun1={ids_per_run[0]}\nrun2={ids_per_run[1]}"
    )
    assert ids_per_run[0], "No points were upserted"


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 — langfuse_bootstrap exits 0 when module missing
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_langfuse_bootstrap_noop_when_module_missing(capsys, monkeypatch):
    """When app.instructions.langfuse_sync is unavailable, bootstrap prints the documented
    log line and exits 0 (does NOT raise or call sys.exit with non-zero)."""
    # Remove any cached module so our monkeypatch takes effect
    for key in list(sys.modules.keys()):
        if "langfuse_bootstrap" in key or "langfuse_sync" in key or "app.instructions" in key:
            del sys.modules[key]

    # Ensure the import of app.instructions.langfuse_sync raises ImportError
    real_import = builtins_import = __builtins__.__class__.__mro__  # just a ref; we use builtins below

    import builtins

    original_import = builtins.__import__

    def _patched_import(name, *args, **kwargs):
        if name == "app.instructions.langfuse_sync" or (
            name == "app.instructions" and args and "langfuse_sync" in (args[2] or [])
        ):
            raise ImportError("simulated missing module")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _patched_import)

    # Import langfuse_bootstrap under the patched import
    if "scripts.langfuse_bootstrap" in sys.modules:
        del sys.modules["scripts.langfuse_bootstrap"]

    import scripts.langfuse_bootstrap as lb_mod

    # reload to pick up monkeypatched import
    importlib.reload(lb_mod)

    # The module-level run() function (or calling main()) must print the deferred line
    captured = capsys.readouterr()
    # Some implementations print at import time; others expose run()
    output = captured.out + captured.err
    if hasattr(lb_mod, "run"):
        lb_mod.run()
        captured = capsys.readouterr()
        output = captured.out + captured.err

    EXPECTED_LOG = "Langfuse bootstrap deferred"
    assert EXPECTED_LOG in output, (
        f"Expected '{EXPECTED_LOG}' in output, got: {output!r}"
    )
