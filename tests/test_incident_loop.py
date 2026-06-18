"""10 tests for the Incident Loop distiller — Task D3.

Tests 1-3: write_incident (incident_logger.py)
Tests 4-10: distill_incidents (incident_distiller.py)

All tests are marked `integration` because they touch SQLite and/or the filesystem.
LLM calls are replaced by a stub via the `llm=` parameter.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import textwrap
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.domain.models import IncidentRecord, LayerEvent, LayerName, ProposedRemediation
from app.observability.layer_event_emitter import LayerEventEmitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(db_path: Path):
    """Build a fresh Repository backed by a tmp_path DB."""
    from app.state.repositories import Repository

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    repo = Repository(conn)
    repo.apply_migrations()
    return repo, conn


def _seed_incident(
    repo,
    *,
    incident_id: str | None = None,
    conversation_id: str = "CONV-TEST",
    triggered_by: str = "verification_failure",
    layer: LayerName = LayerName.VERIFICATION,
    summary: str = "policy_assertion_return_window check failed",
    detail: dict[str, Any] | None = None,
    age_minutes: int = 90,
) -> IncidentRecord:
    """Insert a synthetic IncidentRecord directly into the DB via repo."""
    if incident_id is None:
        incident_id = str(uuid.uuid4())
    created_at = datetime.utcnow() - timedelta(minutes=age_minutes)
    inc = IncidentRecord(
        incident_id=incident_id,
        conversation_id=conversation_id,
        triggered_by=triggered_by,  # type: ignore[arg-type]
        layer=layer,
        summary=summary,
        detail=detail or {"failed_check": "policy_assertion_return_window"},
        created_at=created_at,
    )
    repo.save_incident(inc)
    return inc


def _make_stub_proposal(
    *,
    kind: str = "policy_clarification",
    target_file: str = "data/policy/refund_policy_v1.md",
    source_incident_ids: list[str] | None = None,
    markdown_diff: str | None = None,
) -> dict[str, Any]:
    """Build a valid raw proposal dict as the stub LLM would return."""
    if source_incident_ids is None:
        source_incident_ids = []
    if markdown_diff is None:
        markdown_diff = textwrap.dedent("""\
            --- a/data/policy/refund_policy_v1.md
            +++ b/data/policy/refund_policy_v1.md
            @@ -1,3 +1,6 @@
             # Refund Policy
            +
            +## POLICY-999: Extended clarification
            +
            +Customers must request refunds within the stated return window.

             Standard content.
        """)
    return {
        "kind": kind,
        "target_file": target_file,
        "markdown_diff": markdown_diff,
        "justification": "Three incidents show the return window check is ambiguous.",
        "source_incident_ids": source_incident_ids,
    }


def _make_new_file_diff(target_file: str, content: str) -> str:
    """Build a unified diff that creates a new file."""
    lines = content.splitlines(keepends=True)
    hunk_header = f"@@ -0,0 +1,{len(lines)} @@\n"
    added = "".join(f"+{line}" for line in lines)
    return (
        f"--- /dev/null\n"
        f"+++ b/{target_file}\n"
        f"{hunk_header}"
        f"{added}"
    )


def _build_stub_llm(raw_proposals: list[dict[str, Any]]) -> MagicMock:
    """Return a mock that behaves like AzureChatOpenAI.invoke() / ainvoke()."""
    mock = MagicMock()
    response = MagicMock()
    response.content = json.dumps({"proposals": raw_proposals})
    import asyncio

    async def _ainvoke(*args: Any, **kwargs: Any) -> MagicMock:
        return response

    mock.ainvoke = _ainvoke
    mock.invoke = MagicMock(return_value=response)
    return mock


# ---------------------------------------------------------------------------
# Test 1 — write_incident creates YAML file and DB row
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_write_incident_creates_yaml_file_and_db_row(tmp_path: Path) -> None:
    from app.learning.incident_logger import write_incident

    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    with (
        patch("app.learning.incident_logger._get_incidents_dir", return_value=incidents_dir),
        patch("app.learning.incident_logger._get_repo", return_value=repo),
    ):
        inc_id = write_incident(
            triggered_by="verification_failure",
            layer=LayerName.VERIFICATION,
            summary="test_check: injection detected",
            detail={"failed_check": "injection_check", "payload": "DROP TABLE"},
            conversation_id="CONV-1",
        )

    # YAML file exists
    yaml_files = list(incidents_dir.glob("*.yaml"))
    assert len(yaml_files) == 1, f"Expected 1 YAML file, found {len(yaml_files)}"

    data = yaml.safe_load(yaml_files[0].read_text())
    assert data["incident_id"] == inc_id
    assert data["triggered_by"] == "verification_failure"
    assert data["layer"] == "L9_VERIFICATION"
    assert "injection_check" in str(data["detail"])

    # DB row exists
    cursor = conn.execute("SELECT incident_id FROM incidents WHERE incident_id = ?", (inc_id,))
    assert cursor.fetchone() is not None
    conn.close()


# ---------------------------------------------------------------------------
# Test 2 — write_incident is idempotent on incident_id
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_write_incident_idempotent_on_id(tmp_path: Path) -> None:
    from app.learning.incident_logger import write_incident

    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)
    fixed_id = str(uuid.uuid4())

    with (
        patch("app.learning.incident_logger._get_incidents_dir", return_value=incidents_dir),
        patch("app.learning.incident_logger._get_repo", return_value=repo),
    ):
        write_incident(
            triggered_by="tool_failure",
            layer=LayerName.TOOLS,
            summary="tool_failure: crm_lookup timed out",
            detail={"tool": "crm_lookup"},
            conversation_id="CONV-2",
            incident_id=fixed_id,
        )
        write_incident(
            triggered_by="tool_failure",
            layer=LayerName.TOOLS,
            summary="tool_failure: crm_lookup timed out",
            detail={"tool": "crm_lookup"},
            conversation_id="CONV-2",
            incident_id=fixed_id,
        )

    # Only one file on disk
    yaml_files = list(incidents_dir.glob("*.yaml"))
    assert len(yaml_files) == 1, f"Expected 1 file, found {len(yaml_files)}"

    # Only one row in DB
    cursor = conn.execute(
        "SELECT count(*) FROM incidents WHERE incident_id = ?", (fixed_id,)
    )
    assert cursor.fetchone()[0] == 1
    conn.close()


# ---------------------------------------------------------------------------
# Test 3 — write_incident emits incident_written event
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_write_incident_emits_incident_written_event(tmp_path: Path) -> None:
    from app.learning.incident_logger import write_incident
    import app.observability.layer_event_emitter as emitter_mod

    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    captured: list[LayerEvent] = []
    fake_emitter = LayerEventEmitter()
    fake_emitter.subscribe(lambda ev: captured.append(ev))

    original = emitter_mod._global_emitter
    emitter_mod._global_emitter = fake_emitter

    try:
        with (
            patch("app.learning.incident_logger._get_incidents_dir", return_value=incidents_dir),
            patch("app.learning.incident_logger._get_repo", return_value=repo),
        ):
            inc_id = write_incident(
                triggered_by="hitl_override",
                layer=LayerName.VERIFICATION,
                summary="hitl_override: agent denied; human approved",
                detail={},
                conversation_id="CONV-3",
            )
    finally:
        emitter_mod._global_emitter = original
        conn.close()

    # Exactly one incident_written event with matching incident_id
    written_events = [
        ev
        for ev in captured
        if ev.event_type == "incident_written" and ev.layer == LayerName.INCIDENT_LOOP
    ]
    assert len(written_events) == 1
    assert written_events[0].payload["incident_id"] == inc_id


# ---------------------------------------------------------------------------
# Test 4 — distill skips already-processed incidents
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_skips_already_processed(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    # Seed 3 incidents; mark one as processed
    inc1 = _seed_incident(repo, incident_id="INC-A", age_minutes=120)
    inc2 = _seed_incident(repo, incident_id="INC-B", age_minutes=120)
    inc3 = _seed_incident(repo, incident_id="INC-C", age_minutes=120)
    repo.mark_incident_processed("INC-C", batch_id="prior-run")

    # Stub LLM returns a proposal for INC-A + INC-B
    stub_proposal = _make_stub_proposal(source_incident_ids=["INC-A", "INC-B"])
    stub_llm = _build_stub_llm([stub_proposal])

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    # INC-C was already processed — LLM should only have seen INC-A and INC-B
    assert len(proposals) == 1
    assert "INC-C" not in proposals[0].source_incident_ids
    conn.close()


# ---------------------------------------------------------------------------
# Test 5 — distill respects min_age_minutes filter
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_respects_min_age_filter(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    # Two incidents 30 min old (too fresh), one 90 min old (eligible)
    _seed_incident(repo, incident_id="INC-FRESH-1", age_minutes=30)
    _seed_incident(repo, incident_id="INC-FRESH-2", age_minutes=30)
    _seed_incident(repo, incident_id="INC-OLD", age_minutes=90)

    stub_proposal = _make_stub_proposal(source_incident_ids=["INC-OLD"])
    stub_llm = _build_stub_llm([stub_proposal])

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    # Only INC-OLD should have been in the batch
    all_source_ids = [sid for p in proposals for sid in p.source_incident_ids]
    assert "INC-OLD" in all_source_ids
    assert "INC-FRESH-1" not in all_source_ids
    assert "INC-FRESH-2" not in all_source_ids
    conn.close()


# ---------------------------------------------------------------------------
# Test 6 — distill emits proposals with valid unified diff
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_emits_proposals_with_valid_unified_diff(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    _seed_incident(repo, incident_id="INC-DIFF", age_minutes=90)

    # Craft a new-file diff that will pass git apply --check
    target = "skills/handle_30day_grace.md"
    file_content = textwrap.dedent("""\
        ---
        id: handle_30day_grace
        name: Handle 30-Day Grace Period
        trigger_intent: refund_grace_period
        layer: L8_SKILLS
        version: "1.0"
        ---

        # Handle 30-Day Grace Period

        Apply a 30-day grace extension for VIP customers when the standard window
        has passed by fewer than 30 days.
    """)
    diff_text = _make_new_file_diff(target, file_content)

    stub_proposal = _make_stub_proposal(
        kind="new_skill",
        target_file=target,
        source_incident_ids=["INC-DIFF"],
        markdown_diff=diff_text,
    )
    stub_llm = _build_stub_llm([stub_proposal])

    # Use a tmp repo dir so git apply --check can run cleanly
    repo_dir = tmp_path / "gitrepo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True, capture_output=True, cwd=str(repo_dir)
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True, capture_output=True, cwd=str(repo_dir)
    )

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    assert len(proposals) == 1
    diff = proposals[0].markdown_diff

    # Write diff to temp file and run git apply --check
    diff_file = tmp_path / "test.patch"
    diff_file.write_text(diff, encoding="utf-8")
    result = subprocess.run(
        ["git", "apply", "--check", str(diff_file)],
        capture_output=True,
        cwd=str(repo_dir),
    )
    assert result.returncode == 0, (
        f"git apply --check failed:\nstdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}\ndiff:\n{diff}"
    )
    conn.close()


# ---------------------------------------------------------------------------
# Test 7 — distill proposes policy_clarification when pattern matches
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_proposes_policy_clarification_when_pattern_matches(
    tmp_path: Path,
) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    # Seed 3 incidents with the same failed_check
    for i in range(3):
        _seed_incident(
            repo,
            incident_id=f"INC-POL-{i}",
            summary="policy_assertion_return_window: window exceeded",
            detail={"failed_check": "policy_assertion_return_window"},
            age_minutes=90,
        )

    stub_proposal = _make_stub_proposal(
        kind="policy_clarification",
        target_file="data/policy/refund_policy_v1.md",
        source_incident_ids=["INC-POL-0", "INC-POL-1", "INC-POL-2"],
    )
    stub_llm = _build_stub_llm([stub_proposal])

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    assert len(proposals) == 1
    assert proposals[0].kind == "policy_clarification"
    assert proposals[0].target_file == "data/policy/refund_policy_v1.md"
    assert set(proposals[0].source_incident_ids) == {"INC-POL-0", "INC-POL-1", "INC-POL-2"}
    conn.close()


# ---------------------------------------------------------------------------
# Test 8 — distill marks incidents as processed after emit
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_marks_incidents_processed_after_emit(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    inc1 = _seed_incident(repo, incident_id="INC-MARK-1", age_minutes=90)
    inc2 = _seed_incident(repo, incident_id="INC-MARK-2", age_minutes=90)

    stub_proposal = _make_stub_proposal(
        source_incident_ids=["INC-MARK-1", "INC-MARK-2"]
    )
    stub_llm = _build_stub_llm([stub_proposal])

    await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    # Both incidents must now appear in processed_incidents
    cursor = conn.execute(
        "SELECT incident_id FROM processed_incidents WHERE incident_id IN (?, ?)",
        ("INC-MARK-1", "INC-MARK-2"),
    )
    processed_ids = {row[0] for row in cursor.fetchall()}
    assert "INC-MARK-1" in processed_ids
    assert "INC-MARK-2" in processed_ids
    conn.close()


# ---------------------------------------------------------------------------
# Test 9 — distill handles empty incident pool
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_handles_empty_incident_pool(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    # No incidents at all
    stub_llm = _build_stub_llm([])  # would fail if called
    stub_llm.ainvoke = MagicMock(side_effect=AssertionError("LLM must not be called"))

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=tmp_path / "proposals",
    )

    assert proposals == []
    conn.close()


# ---------------------------------------------------------------------------
# Test 10 — distill writes proposals to data/proposals/ directory
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_distill_writes_proposals_to_data_proposals_directory(tmp_path: Path) -> None:
    from app.learning.incident_distiller import distill_incidents

    db_path = tmp_path / "state.db"
    repo, conn = _make_repo(db_path)

    _seed_incident(repo, incident_id="INC-WRITE", age_minutes=90)

    proposals_dir = tmp_path / "proposals"
    stub_proposal = _make_stub_proposal(
        kind="policy_clarification",
        source_incident_ids=["INC-WRITE"],
    )
    stub_llm = _build_stub_llm([stub_proposal])

    proposals = await distill_incidents(
        min_age_minutes=60,
        batch_size=10,
        llm=stub_llm,
        repo=repo,
        proposals_dir=proposals_dir,
    )

    assert len(proposals) == 1
    written_files = list(proposals_dir.glob("*.md"))
    assert len(written_files) == 1, f"Expected 1 proposal file, found {len(written_files)}"

    # Filename contains the kind
    assert "policy_clarification" in written_files[0].name

    # File content includes the diff
    content = written_files[0].read_text()
    assert "markdown_diff" in content or "diff" in content.lower()
    conn.close()
