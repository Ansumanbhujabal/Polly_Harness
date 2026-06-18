"""Push prompts to Langfuse.

Wave 1 bootstrap:  app.instructions.langfuse_sync is built in Wave 2.
If the module is not yet present this script exits 0 with a documented
log line so that CI / Makefile targets don't break before Wave 2 lands.

Usage:
    python scripts/langfuse_bootstrap.py

Exit codes:
    0 — always (success or graceful deferred)
"""

from __future__ import annotations

import sys


def run() -> None:
    """Attempt to push all prompts to Langfuse.

    If the underlying module is not yet built (Wave 2), print the
    documented deferred-bootstrap message and return without error.
    """
    try:
        from app.instructions.langfuse_sync import push_all_prompts  # type: ignore[import]
    except ImportError:
        print("Langfuse bootstrap deferred — app.instructions not yet built.")
        return

    push_all_prompts()
    print("[langfuse_bootstrap] All prompts pushed to Langfuse.")


if __name__ == "__main__":
    run()
    sys.exit(0)
