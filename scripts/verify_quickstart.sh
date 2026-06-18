#!/usr/bin/env bash
# verify_quickstart.sh — end-to-end smoke test for a clean-clone quickstart.
#
# What this script tests
# ──────────────────────
#  1. uv sync            — dependency installation is reproducible
#  2. seed_qdrant.py     — policy doc chunks + embeds to Qdrant
#  3. uvicorn            — API server starts (Wave 3; will FAIL until app.api.main exists)
#  4. /healthz           — HTTP 200 smoke check
#
# TODO (Wave 4 burn-in)
# ──────────────────────
#  • Extend to POST /refund with a fixture payload and assert JSON response.
#  • Replace the inline `sleep 5` with a proper readiness poll loop.
#  • Wire into CI as a Docker-compose integration target.
#
# NOTE: Steps 3-4 are expected to fail until Wave 3 (app.api) is built.
#       The script is intentionally shipped early so Wave 3 can be verified
#       by running it without any other changes.
#
# Usage:
#   chmod +x scripts/verify_quickstart.sh
#   ./scripts/verify_quickstart.sh

set -euo pipefail

UV=${UV:-uv}

echo "[verify_quickstart] Step 1: uv sync"
$UV sync --extra dev

echo "[verify_quickstart] Step 2: seed_qdrant.py"
$UV run python scripts/seed_qdrant.py

# Steps 3-4 require Wave 3 (app.api.main). They will fail until then.
echo "[verify_quickstart] Step 3: start uvicorn (Wave 3+ only)"
$UV run uvicorn app.api.main:app --port 7900 &
SERVER_PID=$!

echo "[verify_quickstart] Waiting 5 s for server to be ready…"
sleep 5

echo "[verify_quickstart] Step 4: /healthz smoke check"
curl -fsS http://localhost:7900/healthz

echo "[verify_quickstart] All checks passed."

kill "$SERVER_PID" 2>/dev/null || true
