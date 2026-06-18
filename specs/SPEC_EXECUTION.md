# SPEC: Execution Environment

**Layer:** L4 — Execution Environment
**Owner:** `app/tools/executor.py` (sandbox executor) + `Dockerfile` + `docker-compose.yml` + `app/api/lifespan.py` (boot order)

The Execution Environment layer is *where* the agent's actions happen. It defines the runtime container, the network boundary, the boot/shutdown order of the moving parts, and the per-tool sandbox envelope. The executor itself (the per-call timeout + retry + structured-error wrapper) is fully specified in `SPEC_TOOLS.md`; this spec owns everything **around** the executor: the process boundary, the deployment artifact, the lifecycle of in-process dependencies.

## Contract

The Execution Environment layer is not a Python module you import — it is a contract over runtime invariants. The exports it *coordinates* are:

```python
from app.tools.executor import run_tool       # owned by SPEC_TOOLS
from app.api.lifespan import lifespan          # owned here (boot order)
```

`lifespan(app: FastAPI) -> AsyncIterator[None]` runs the boot sequence on startup and the reverse on shutdown. The exact order is the contract.

## The boot order

On FastAPI startup, `lifespan` runs these steps **in order**, awaiting each before the next begins:

1. `_check_qdrant_health()` — issues a single `GET /healthz` to `settings.QDRANT_URL`; raises `RuntimeError("Qdrant unreachable at <url>")` on non-200. Catches collection-missing as a separate WARN (the seeding script is a developer concern, not a runtime crash).
2. `_apply_sqlite_migrations()` — calls `app.state.migrations.runner.apply_all()`. Idempotent per `SPEC_STATE`.
3. `_langfuse_handshake()` — calls `app.observability.get_langfuse_client()` and issues a no-op span to confirm the API key is valid. If `settings.langfuse_configured` is False, logs WARN and continues (the system runs without Langfuse).
4. `_start_mcp_server()` — spawns the in-process MCP server task per `SPEC_MCP_SERVER.mcp_lifespan_task()`. Records the task handle on `app.state.mcp_task`.

After step 4, `lifespan` yields control to FastAPI; HTTP traffic begins.

On shutdown, the reverse order runs:

1. Cancel `app.state.mcp_task` and await it.
2. Flush Langfuse pending spans via `client.flush(timeout=5.0)`.
3. Close the SQLite connection pool.
4. (Qdrant check is read-only; no shutdown step needed.)

Reverse-order is asserted in tests — it is the contract, not an implementation detail.

## Network egress lockdown

The container's outbound network is restricted to three hosts:

- `*.openai.azure.com` (Azure OpenAI)
- `cloud.langfuse.com` and `*.langfuse.com` (Langfuse)
- The Qdrant container hostname (private network only)

This whitelist is enforced **two ways**:

- **In tests:** `respx` blocks unmocked hosts; any test that accidentally reaches out to a real host fails with `respx.RouteNotFound`.
- **In production deploy:** HF Spaces does not provide native egress filtering, so this is documented as a roadmap item — a production deployment behind a proper VPC would add an iptables egress rule. The spec captures the intent so that the codebase is *ready* for it (no hardcoded URLs outside `app/config.Settings`).

The executor's structured error envelope already surfaces a `error_code="NETWORK_BLOCKED"` when a tool tries to reach a non-whitelisted host in a test that simulates the lockdown — implemented in `SPEC_TOOLS.executor`.

## The Dockerfile contract

The `Dockerfile` is multi-stage:

```dockerfile
# --- builder stage ---
FROM python:3.11-slim AS builder
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# --- runtime stage ---
FROM python:3.11-slim AS runtime
RUN useradd --uid 1000 --create-home appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser frontend/ ./frontend/
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser agentic.md prompts/ skills/ ./
USER appuser
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:7860/healthz || exit 1
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

Constraints captured by the spec:

- **Multi-stage** — final image excludes `uv` and build artifacts; only the venv + source ships.
- **Non-root** — `appuser` (uid 1000) is the process owner. No `USER root` in the final stage.
- **Healthcheck** — the Docker `HEALTHCHECK` directive must be present and curl `/healthz`.
- **No `.git/`, no test files** in the runtime image (the `COPY` lines name only production paths).
- **Slim base** — `python:3.11-slim` to keep image size predictable.

## The docker-compose contract

`docker-compose.yml` defines two services on a private network:

```yaml
services:
  app:
    build: .
    ports: ["7860:7860"]
    environment: [...]   # forwards .env values
    depends_on: [qdrant]
    networks: [refund_net]
  qdrant:
    image: qdrant/qdrant:v1.12.4
    expose: ["6333"]     # NOT ports — internal only
    networks: [refund_net]
    volumes: [qdrant_data:/qdrant/storage]

networks:
  refund_net:
    driver: bridge

volumes:
  qdrant_data:
```

Constraint: `qdrant` uses `expose` (intra-network) not `ports` (host-published). Only `app` publishes to the host.

## Events emitted

- `L4_EXECUTION / boot_step_completed` — payload: `{step: "qdrant_health" | "sqlite_migrate" | "langfuse_handshake" | "mcp_server_start", latency_ms: float}` — one emit per step.

Tool-level events (`tool_invoked`, `tool_succeeded`, `tool_retry`, `tool_failed`) are owned by `SPEC_TOOLS`.

## Files

```
Dockerfile                       # modified — multi-stage + non-root + healthcheck
docker-compose.yml               # modified — private network + qdrant expose-only
app/api/lifespan.py              # created — boot order owned here
tests/test_execution.py          # created — 5 tests below
```

## Dependencies

- `app.state.migrations.runner.apply_all` (from `SPEC_STATE`)
- `app.observability.get_langfuse_client` (from `SPEC_OBSERVABILITY`)
- `app.mcp.mcp_lifespan_task` (from `SPEC_MCP_SERVER`)
- `app.config.settings` for `QDRANT_URL`, Langfuse config flags
- `httpx.AsyncClient` for the Qdrant health probe
- `respx` (dev) for egress-block test fixtures

Out of scope: the executor itself (owned by `SPEC_TOOLS`).

## Tests

`tests/test_execution.py` — minimum tests:

1. `test_lifespan_runs_qdrant_health_before_migrations` — patches each boot step with an async mock; asserts the call order via a recorded call-log list.
2. `test_lifespan_runs_migrations_before_langfuse_handshake` — same call-log technique.
3. `test_lifespan_emits_boot_step_completed_per_stage` — captures emitted `LayerEvent` instances via a fake emitter; asserts 4 emits with the 4 step names.
4. `test_lifespan_shutdown_reverses_order` — runs lifespan as a context manager; asserts shutdown call-log is the reverse of startup.
5. `test_dockerfile_uses_non_root_user` — parses `Dockerfile` text; asserts `USER appuser` appears AFTER the final `FROM` line and BEFORE `CMD`; asserts `HEALTHCHECK` directive is present.

Use `pytest-asyncio` for the lifespan tests; no real Qdrant/Langfuse contact.

## Done criteria

- [ ] `Dockerfile` is multi-stage with non-root `appuser` (uid 1000) and a `HEALTHCHECK` directive curling `/healthz`.
- [ ] `docker-compose.yml` defines `app` + `qdrant` on a private bridge network; `qdrant` is `expose`-only (no host port).
- [ ] `app/api/lifespan.py` exists and runs the four boot steps in the documented order, with reverse-order shutdown.
- [ ] All 5 tests pass under `pytest -m "unit or integration" tests/test_execution.py`.
- [ ] `docker compose build` succeeds in <5 minutes from a clean docker cache (measured once during integration burn).
- [ ] No tool imports from `app.graph`, `app.mcp`, or `app.api` other than the lifespan-imports listed in Dependencies (one-way dependency).
