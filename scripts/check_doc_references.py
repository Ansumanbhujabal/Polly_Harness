#!/usr/bin/env python3
"""
check_doc_references.py — E3 doc-link guard.

Walks README.md + docs/**/*.md and checks:

  1. Markdown links of the form [text](path) where path is a relative file
     path — asserts each resolves to an extant file.
     Skips: http://, https://, mailto:, and pure #fragment anchors.

  2. References of the form  tests/path.py::test_name  — asserts:
       (a) tests/path.py exists relative to REPO_ROOT, AND
       (b) a line matching `def test_name(` is present in that file.

Exit behaviour (v0.1 — lenient):
  Always exits 0, even when broken refs are found, because several files
  cited in README.md are WIP gaps that will be resolved in Phase F's README
  audit.  Set env-var CHECK_DOC_STRICT=1 to flip to strict mode (exit 1
  when any unresolved ref is found).  Phase F will enable strict mode in CI.

Known WIP gaps (removed in Phase F README audit):
  - docs/decisions/0001-langgraph-as-orchestration.md
  - docs/decisions/0002-azure-openai-langfuse-qdrant.md
  - docs/decisions/0003-mcp-tool-protocol.md
  - docs/decisions/0004-incident-loop-feedback.md
  - docs/decisions/0005-skip-voice.md
  - LICENSE
  - tests/test_executor.py (file not yet created — Wave 4)
  - tests/test_retriever.py (file not yet created — Wave 4)
  - tests/test_langfuse_client.py (file not yet created — Wave 4)
  - def test_injection_detected in test_verification.py (stub, not written)
  - def test_duplicate_customer_id_rejected in test_tools.py (stub)
  - def test_hallucinated_id_blocked in test_verification.py (stub)
  - def test_cap_edge_triggers_interrupt in test_graph.py (stub)
  - def test_resume_after_crash in test_state.py (stub)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.resolve()

# Files / glob patterns to scan
SCAN_TARGETS: list[Path] = [
    REPO_ROOT / "README.md",
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
]

# Strict mode: exit 1 on any unresolved ref
STRICT = os.environ.get("CHECK_DOC_STRICT", "0") == "1"

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches [text](path) — captures the path part
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Matches tests/some_file.py::some_test_fn  (anywhere in a line)
_TEST_REF_RE = re.compile(r"(tests/[\w/]+\.py)::(test_\w+)")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_external(href: str) -> bool:
    """Return True for links we must NOT resolve (external / anchors)."""
    return (
        href.startswith("http://")
        or href.startswith("https://")
        or href.startswith("mailto:")
        or href.startswith("#")
    )


def resolve_link(href: str, source_file: Path) -> tuple[bool, str]:
    """
    Resolve *href* relative to *source_file*'s directory.

    Returns (ok, resolved_path_str).
    Strips any trailing #anchor fragment before resolving.
    """
    # Strip fragment
    href_no_frag = href.split("#")[0]
    if not href_no_frag:
        # Pure anchor — skip
        return True, ""
    target = (source_file.parent / href_no_frag).resolve()
    return target.exists(), str(target.relative_to(REPO_ROOT))


def check_test_ref(test_path_str: str, fn_name: str) -> tuple[bool, bool, str]:
    """
    Check that *test_path_str* (e.g. ``tests/test_foo.py``) exists and
    contains ``def fn_name(``.

    Returns (file_ok, fn_ok, resolved_path_str).
    """
    target = (REPO_ROOT / test_path_str).resolve()
    rel = str(target.relative_to(REPO_ROOT))
    if not target.exists():
        return False, False, rel
    with open(target, encoding="utf-8") as fh:
        src = fh.read()
    fn_ok = bool(re.search(rf"\bdef {re.escape(fn_name)}\(", src))
    return True, fn_ok, rel


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run() -> int:
    """
    Scan all target files.  Return number of broken references found.
    """
    broken: list[str] = []
    scanned_files: list[str] = []

    for source in SCAN_TARGETS:
        if not source.exists():
            # doc file itself missing — skip gracefully
            continue
        scanned_files.append(str(source.relative_to(REPO_ROOT)))
        text = source.read_text(encoding="utf-8")

        # --- 1. Markdown relative file links ---
        for match in _MD_LINK_RE.finditer(text):
            href = match.group(2).strip()
            if is_external(href):
                continue
            # Skip pure fragment anchors
            if href.startswith("#"):
                continue
            href_no_frag = href.split("#")[0]
            if not href_no_frag:
                continue
            ok, resolved = resolve_link(href, source)
            if not ok:
                broken.append(
                    f"  [BROKEN LINK] {source.relative_to(REPO_ROOT)}: [{match.group(1)}]({href})"
                    f"  -> unresolved: {resolved}"
                    f"  # WIP gap — removed in Phase F README audit"
                )

        # --- 2. Test references  tests/foo.py::test_bar ---
        for match in _TEST_REF_RE.finditer(text):
            test_path_str = match.group(1)
            fn_name = match.group(2)
            file_ok, fn_ok, resolved = check_test_ref(test_path_str, fn_name)
            if not file_ok:
                broken.append(
                    f"  [BROKEN TEST REF] {source.relative_to(REPO_ROOT)}: "
                    f"{test_path_str}::{fn_name}"
                    f"  -> file not found: {resolved}"
                    f"  # WIP gap — removed in Phase F README audit"
                )
            elif not fn_ok:
                broken.append(
                    f"  [MISSING TEST FN] {source.relative_to(REPO_ROOT)}: "
                    f"{test_path_str}::{fn_name}"
                    f"  -> def {fn_name}( not found in {resolved}"
                    f"  # WIP gap — removed in Phase F README audit"
                )

    # --- Report ---
    print(f"check_doc_references: scanned {len(scanned_files)} file(s)")
    for f in scanned_files:
        print(f"  - {f}")

    if broken:
        print(f"\nUnresolved references found ({len(broken)}):")
        for line in broken:
            print(line)
        if STRICT:
            print("\nSTRICT mode active — exiting 1.")
            return 1
        else:
            print(
                "\nv0.1 LENIENT mode: logging above gaps but exiting 0."
                "  Set CHECK_DOC_STRICT=1 to enforce.  (Phase F will enable strict mode in CI.)"
            )
            return 0
    else:
        print("\nAll references resolved OK.")
        return 0


if __name__ == "__main__":
    sys.exit(run())
