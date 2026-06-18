# SPEC: Instructions Layer

**Layer:** L1 — Instructions
**Owner:** `app/instructions/`

The Instructions layer is the single source of truth for every prompt string in the harness. It owns the system prompt, all task-specific sub-prompts, and the Langfuse prompt registry integration that keeps remote and local versions in sync. Every other layer that needs a prompt string imports it from here — no layer may inline a raw prompt string outside this module.

## Contract

The Instructions layer exports three callables to the rest of the system:

```python
from app.instructions import load_system_prompt, load_skill_router_prompt, get_prompt_version
```

- `load_system_prompt(version: str | None = None) -> str` — returns the resolved system prompt string. When `settings.LANGFUSE_CONFIGURED` is true, fetches the prompt from Langfuse by name `"system_refund_agent"`. When it is false (clean clone, no credentials), reads the local `prompts/system_refund_agent.md` file and returns its contents. Version `None` means "latest production label" in Langfuse terminology; a semver string (e.g., `"1.2.0"`) pins to an exact version. Raises `RuntimeError` only if both Langfuse and the local fallback file are absent.
- `load_skill_router_prompt(version: str | None = None) -> str` — same resolution logic, but targets the `"intent_classifier"` prompt. Named `load_skill_router_prompt` because the orchestration layer calls it when routing by intent; the underlying prompt file is `prompts/intent_classifier.md`.
- `get_prompt_version() -> str` — returns the version string that was last resolved by either loader, for use in trace tagging. If no prompt has been loaded in the current process lifetime, returns `"local-unversioned"`.

No other public symbols are exported from `app/instructions/__init__.py`. Internal helpers (`_load_from_langfuse`, `_load_from_disk`, `_hash_content`) are private.

## Inputs / Outputs

This layer consumes no cross-layer domain objects — it is the bottom of the dependency graph. Its outputs are plain `str` values (prompt text) and one `LayerEvent` per load.

The event payload uses these field names (all standard Python primitives, not Pydantic models):

| Field | Type | Example |
|---|---|---|
| `name` | `str` | `"system_refund_agent"` |
| `version` | `str` | `"1.2.0"` or `"local-unversioned"` |
| `source` | `Literal["langfuse", "local"]` | `"langfuse"` |

The emitter call signature (for reference when reading `loader.py`):

```python
emitter.emit(LayerEvent(
    conversation_id=conversation_id,
    layer=LayerName.INSTRUCTIONS,
    event_type="prompt_loaded",
    payload={"name": name, "version": version, "source": source},
))
```

`LayerName` and `LayerEvent` are imported from `app.domain.models`. Do not redefine them.

## Behaviors

### Langfuse-first resolution with local fallback

On every `load_system_prompt` or `load_skill_router_prompt` call, the loader attempts Langfuse first. If `settings.LANGFUSE_CONFIGURED` is false (any of `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` absent from the environment), the Langfuse path is skipped entirely and the local file is read from disk. The loader logs at `WARN` level when skipping Langfuse:

```
WARN [app.instructions.loader] Langfuse not configured — falling back to local prompts/system_refund_agent.md
```

This fallback is unconditional: a clean clone with no `.env` must boot and serve prompts without errors.

### In-memory TTL cache

Resolved prompts are cached in a module-level dictionary keyed on `(prompt_name, version)`. The cache entry expires after `settings.PROMPT_CACHE_TTL_SECONDS` seconds (default `300`). On the next call after expiry, the loader re-fetches from Langfuse (or disk) and refreshes the cache entry. The TTL clock uses `time.monotonic()`. Cache misses are logged at `DEBUG` level.

### Langfuse sync on startup (`langfuse_sync.py`)

`app/instructions/langfuse_sync.py` exports one function:

```python
def sync_prompts_to_langfuse() -> None:
    """Read local prompts/*.md, compare SHA-256 hash of content to the
    current-production version in Langfuse, and push a new version only
    if the hash differs. Idempotent: calling this N times with unchanged
    files produces exactly one version in Langfuse."""
```

This function is called in two places:
1. `scripts/langfuse_bootstrap.py` — manual bootstrap, run once per environment setup.
2. FastAPI lifespan startup — when `settings.LANGFUSE_PROMPT_AUTOSYNC=true`.

If `settings.LANGFUSE_CONFIGURED` is false, `sync_prompts_to_langfuse()` is a no-op (logs `INFO` and returns immediately). It must not raise.

### Prompt files shipped in `prompts/`

The builder must create the following files. Each file contains a complete, standalone prompt string — no template variables, no placeholders. The content is illustrative; the builder writes sensible stubs that can be iterated on:

- `prompts/system_refund_agent.md` — the main agentic system prompt (the harness root `agentic.md` is the canonical source; this file mirrors its content for the Langfuse sync path)
- `prompts/intent_classifier.md` — a short prompt used by the skill router to classify incoming messages into `refund_request | exchange_request | inquiry | off_topic`
- `prompts/denial_rewriter.md` — a prompt that rewrites a raw denial decision into empathetic, policy-cited customer language
- `prompts/fraud_check_subagent.md` — the system prompt for the fraud-check sub-agent (L7); loaded here so all prompts share one registry

The builder must not hardcode these strings anywhere in Python source. Every layer that needs a prompt string calls `load_system_prompt` or the analogous loader for that prompt.

## Events emitted

- `L1_INSTRUCTIONS / prompt_loaded` — emitted once per cache miss (i.e., on every actual fetch, not on cache hits). Payload: `name`, `version`, `source` as described above.

No other events are emitted by this layer. The layer does not emit startup or shutdown lifecycle events; those belong to the FastAPI lifespan layer.

## Files

```
app/instructions/
├── __init__.py          # exports load_system_prompt, load_skill_router_prompt,
│                        # get_prompt_version (nothing else)
├── loader.py            # local-disk + Langfuse merge logic, TTL cache
└── langfuse_sync.py     # hash-and-push to Langfuse prompt registry

prompts/
├── system_refund_agent.md
├── intent_classifier.md
├── denial_rewriter.md
└── fraud_check_subagent.md
```

Total: 3 Python module files + 4 prompt markdown files = 7 files to create. The `prompts/` directory already exists in the repo root.

## Dependencies

- `app.domain.models` — `LayerName`, `LayerEvent`
- `app.observability` — `get_emitter`, `get_logger`
- `app.config` — `settings` (reads `LANGFUSE_CONFIGURED`, `PROMPT_CACHE_TTL_SECONDS`, `LANGFUSE_PROMPT_AUTOSYNC`)

Out of scope for this layer: `app.graph`, `app.api`, `app.mcp`. Instructions is the innermost layer; it must not import from any of those. Violation breaks the one-way dependency rule and the builder's `mypy --strict` check will catch it (no circular imports allowed).

## Tests

`tests/test_instructions.py` — minimum 7 tests:

1. `test_loader_returns_local_when_langfuse_unconfigured` — with `LANGFUSE_HOST` unset in the environment, `load_system_prompt()` returns the text of the local `prompts/system_refund_agent.md` file without raising.
2. `test_loader_prefers_langfuse_when_configured` — mock `langfuse.Langfuse.get_prompt` to return a sentinel string; assert `load_system_prompt()` returns that sentinel when Langfuse env vars are present.
3. `test_cache_hit_within_ttl` — call `load_system_prompt()` twice; assert the underlying fetch (Langfuse or disk) is called exactly once (i.e., second call is a cache hit).
4. `test_cache_expiry_after_ttl` — use `freezegun` to advance time past `PROMPT_CACHE_TTL_SECONDS`; assert the underlying fetch is called a second time after expiry.
5. `test_langfuse_sync_pushes_new_when_hash_differs` — mock Langfuse `get_prompt` to return content with a different hash than the local file; assert `create_prompt` (or equivalent push method) is called once.
6. `test_langfuse_sync_noop_when_hash_matches` — mock Langfuse `get_prompt` to return content with the same hash as the local file; assert no push call is made.
7. `test_prompt_loaded_event_emitted_with_version` — after `load_system_prompt()`, assert that the event emitter received exactly one `LayerEvent` with `layer=LayerName.INSTRUCTIONS`, `event_type="prompt_loaded"`, and `payload["source"]` set to either `"langfuse"` or `"local"`.

All tests run with `pytest -m "unit or integration" tests/test_instructions.py`. Tests must not hit the real Langfuse API or the real file system outside the repo's `prompts/` directory. Use `tmp_path` fixtures or monkeypatching as appropriate.

## Done criteria

- [ ] All 5 module files (`app/instructions/__init__.py`, `app/instructions/loader.py`, `app/instructions/langfuse_sync.py`) + 4 prompt files (`prompts/system_refund_agent.md`, `prompts/intent_classifier.md`, `prompts/denial_rewriter.md`, `prompts/fraud_check_subagent.md`) exist on disk.
- [ ] Public surface matches Contract exports exactly: `from app.instructions import load_system_prompt, load_skill_router_prompt, get_prompt_version` succeeds with no `ImportError`.
- [ ] All 7 tests pass under `pytest -m "unit or integration" tests/test_instructions.py`.
- [ ] No imports from `app.graph`, `app.api`, or `app.mcp` anywhere inside `app/instructions/` (one-way dependency only).
- [ ] `mypy --strict app/instructions/` passes (best-effort; known external stubs gaps documented in a comment).
