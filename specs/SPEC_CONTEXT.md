# SPEC: Context Delivery & Management Layer

**Layer:** L2 — Context Delivery & Management
**Owner:** `app/context/`

The Context layer is responsible for three independent but coordinated concerns: retrieving relevant policy clauses from the vector store, projecting a minimal customer snapshot for prompt injection with PII redacted, and keeping the conversation message list within a safe token budget. Every other layer that needs policy text or a customer prompt-dict imports it from here — no layer may inline its own Qdrant call, its own PII redaction logic, or its own token-trimming loop.

## Contract

The Context layer exports three callables to the rest of the system:

```python
from app.context import get_retriever, build_customer_context, compact_messages
```

- `get_retriever() -> PolicyRetriever` — returns the singleton `PolicyRetriever` instance. The singleton is lazy-loaded on first call. Subsequent calls return the same object without re-initialising it. `PolicyRetriever` is defined in `app/context/retriever.py` and is **not** a cross-layer domain model; do not add it to `app/domain/models.py`.

- `build_customer_context(customer: Customer, order: Order | None) -> dict[str, Any]` — returns a small dictionary ready for prompt-injection. It never returns the full `Customer` object. PII fields are redacted before the dict is assembled: `email` is reduced to first-letter-plus-domain (e.g. `j***@example.com`), and `phone` is reduced to the last 4 digits (e.g. `***-1234`). When `order` is `None` the returned dict contains no order keys.

- `compact_messages(messages: list[dict], max_tokens: int) -> list[dict]` — trims a conversation message list to stay within `max_tokens`. Uses `tiktoken` with the `cl100k_base` encoding. When the total token count is already at or below `max_tokens`, the list is returned unchanged (no LLM call is made). When trimming is required, the function preserves the system message and the last 3 conversation turns, then produces a single LLM-summarised message that replaces the middle section, and returns the reconstructed list.

No other public symbols are exported from `app/context/__init__.py`. Internal helpers (`_count_tokens`, `_summarise_middle`, `_redact_email`, `_redact_phone`) are private.

## Inputs / Outputs

### `PolicyRetriever.search`

```python
await retriever.search(query: str, top_k: int = 5) -> list[PolicyClause]
```

`PolicyClause` is imported from `app.domain.models`. The retriever must populate `clause_id` from the chunk metadata field `clause_id`, which follows the pattern `POLICY-NNN` (e.g. `POLICY-008`). The `relevance_score` field is populated from the Qdrant score. Do not invent a new shape — `PolicyClause` is the return type.

### `build_customer_context` inputs

`Customer` and `Order` are imported from `app.domain.models`. The function signature must accept `order: Order | None` — callers pass `None` when no order has been resolved yet. The return type is `dict[str, Any]`; the exact keys are an implementation detail, but the dict must not contain the raw `email` or `phone` strings.

### `compact_messages` inputs

`messages` follows the OpenAI chat message format: each element is a plain `dict` with at minimum a `"role"` key. The function is agnostic of the schema beyond role-awareness; it does not import any domain model. `max_tokens` defaults to `settings.COMPACTION_TOKEN_THRESHOLD` (default `4000`) when callers do not supply it.

### Events

Event payloads use plain Python primitives. `LayerName` and `LayerEvent` are imported from `app.domain.models`. Do not redefine them.

| Event | Payload fields |
|---|---|
| `L2_CONTEXT / retrieval_performed` | `query: str`, `top_k: int`, `latency_ms: float`, `returned_clauses: int` |
| `L2_CONTEXT / compaction_triggered` | `pre_tokens: int`, `post_tokens: int` |

The emitter call pattern (for reference when reading `retriever.py` and `compactor.py`):

```python
emitter.emit(LayerEvent(
    conversation_id=conversation_id,
    layer=LayerName.CONTEXT,
    event_type="retrieval_performed",
    payload={"query": query, "top_k": top_k, "latency_ms": latency_ms, "returned_clauses": len(clauses)},
))
```

## Behaviors

### Retriever initialisation

`PolicyRetriever` wraps `fastembed.TextEmbedding` with model `BAAI/bge-small-en-v1.5`. The retriever does **not** use Azure OpenAI embeddings — the fastembed model is deterministic, runs locally, and consumes no quota. Do not add an Azure embedding client to this class.

On the first call to `get_retriever()`, after the singleton is constructed, the retriever verifies that the Qdrant collection named `settings.QDRANT_COLLECTION_POLICY` exists. If the collection is absent, the retriever raises:

```python
raise RuntimeError("Run `make seed` first")
```

The error message must be exactly `Run \`make seed\` first` — this string is tested verbatim. Do not raise a different exception type or a different message.

### Retriever search

`search` embeds `query` with the local fastembed model, queries Qdrant for the top-`top_k` nearest chunks, extracts `clause_id` from each chunk's payload metadata, populates `relevance_score` from the Qdrant distance score, and returns a `list[PolicyClause]`. The method is `async`; if the underlying Qdrant client is synchronous, wrap the call in `asyncio.to_thread`.

The `retrieval_performed` event is emitted after every successful `search` call. Latency is measured from just before the embed call to just after the Qdrant response returns.

### PII redaction rules

`build_customer_context` applies two redaction rules before constructing the dict:

- **Email**: keep the first character of the local part, replace the rest of the local part with `***`, keep the `@domain` as-is. Example: `jane.doe@example.com` → `j***@example.com`.
- **Phone**: keep only the last 4 characters of the raw phone string, prefix with `***-`. Example: `+91-98765-43210` → `***-3210`. If the phone field is empty or shorter than 4 characters, set the redacted value to `***`.

When `order` is `None`, the returned dict must not contain any order-related keys (no `order_id`, no `status`, no `items`). When an order is present, include a compact order summary — order ID, status, total, and item names — sufficient for the prompt but not the full `Order` object.

### Compaction threshold

`compact_messages` counts the total tokens across all messages using `tiktoken`'s `cl100k_base` encoding before doing anything else. If the count is at or below `max_tokens`, the function returns the original list object unchanged — no copy, no LLM call. The `compaction_triggered` event is **not** emitted in this case.

When the count exceeds `max_tokens`:

1. Separate the system message (role `"system"`) from the rest. There is at most one system message; it always survives.
2. Take the last 3 non-system messages as the "tail" — they always survive verbatim.
3. Treat all remaining non-system messages as the "middle". Send the middle to the LLM with an instruction to produce a one-paragraph summary. Replace the middle with a single `{"role": "assistant", "content": "<summary>"}` message.
4. Reassemble: `[system_message] + [summary_message] + tail` (system omitted if absent).
5. Emit `compaction_triggered` with `pre_tokens` (original count) and `post_tokens` (count of the compacted list).

The LLM call for summarisation goes through the same Azure OpenAI client used elsewhere in the harness (`settings.AZURE_OPENAI_*`). The compactor is synchronous; the LangGraph node that calls it is responsible for wrapping it in a threadpool if needed (as noted in the Files section).

## Events emitted

- `L2_CONTEXT / retrieval_performed` — emitted once per successful `search` call. Payload: `query`, `top_k`, `latency_ms`, `returned_clauses` (count, not the objects). Not emitted on error.
- `L2_CONTEXT / compaction_triggered` — emitted once per compaction run (i.e. only when the token count exceeded the threshold and the middle was summarised). Payload: `pre_tokens`, `post_tokens`.

No other events are emitted by this layer.

## Files

```
app/context/
├── __init__.py                  # exports get_retriever, build_customer_context,
│                                # compact_messages (nothing else)
├── retriever.py                 # PolicyRetriever class (fastembed + Qdrant)
├── compactor.py                 # token-counting + LLM summarisation (sync)
└── customer_context_builder.py  # PII redaction + minimal customer projection
```

Total: 4 module files to create.

## Dependencies

- `app.domain.models` — `Customer`, `Order`, `PolicyClause`, `LayerName`, `LayerEvent`
- `app.observability` — `get_emitter`, `get_logger`
- `app.config` — `settings` (reads `QDRANT_COLLECTION_POLICY`, `COMPACTION_TOKEN_THRESHOLD`, `AZURE_OPENAI_*`)
- `fastembed` — `TextEmbedding` (model `BAAI/bge-small-en-v1.5`)
- `qdrant_client` — Qdrant async or sync client
- `tiktoken` — `cl100k_base` encoding
- Azure OpenAI client — for the compaction summarisation LLM call only

Out of scope for this layer: `app.graph`, `app.api`, `app.mcp`, `app.tools`. The Context layer is upstream of Tools (Tools calls `app.context.retriever` for `search_policy`); it must not import from Tools or any layer above it.

## Tests

`tests/test_context.py` — minimum 10 tests:

1. `test_retriever_raises_helpful_error_when_collection_missing` — mock the Qdrant client to report the collection absent; assert `get_retriever()` raises `RuntimeError` with message `"Run \`make seed\` first"`.
2. `test_retriever_returns_top_k_clauses_with_ids` — replay a recorded Qdrant response (via `respx` or `pytest-mock`); assert the returned list is `list[PolicyClause]` with `clause_id` values matching the `POLICY-NNN` format.
3. `test_retriever_emits_event_on_success` — after a successful `search`, assert the emitter received exactly one `LayerEvent` with `layer=LayerName.CONTEXT`, `event_type="retrieval_performed"`, and `payload["returned_clauses"]` equal to the length of the returned list.
4. `test_build_customer_context_redacts_email` — pass a `Customer` with a known email; assert the returned dict contains the redacted form (first-letter + `***@domain`) and not the raw email.
5. `test_build_customer_context_redacts_phone` — pass a `Customer` with a known phone; assert the returned dict contains only the last-4-digit form and not the raw phone number.
6. `test_build_customer_context_omits_order_when_none` — call `build_customer_context(customer, order=None)`; assert no order-related key (`order_id`, `status`, `items`) appears in the returned dict.
7. `test_compact_messages_noop_below_threshold` — pass a short message list whose token count is below `max_tokens`; assert the returned list is the identical object (i.e. `result is messages`) and no LLM call was made.
8. `test_compact_messages_preserves_system_and_last_three_turns` — pass a long message list that exceeds the threshold; assert the system message and the last 3 non-system messages are present verbatim in the compacted result.
9. `test_compact_messages_emits_event_with_token_delta` — after a compaction run, assert the emitter received exactly one `LayerEvent` with `event_type="compaction_triggered"`, `payload["pre_tokens"]` > `payload["post_tokens"]`.
10. `test_compact_messages_idempotent_when_already_compact` — compact a list once, then compact the result again with the same threshold; assert the second call returns unchanged (no second LLM call, no second event).

All tests run with `pytest -m "unit or integration" tests/test_context.py`. No test may make real network calls — Qdrant must be mocked via `respx` or `pytest-mock`, and the LLM summarisation call must be patched.

## Done criteria

- [ ] All 4 module files exist: `app/context/__init__.py`, `app/context/retriever.py`, `app/context/compactor.py`, `app/context/customer_context_builder.py`.
- [ ] Public surface matches Contract exports exactly: `from app.context import get_retriever, build_customer_context, compact_messages` succeeds with no `ImportError`.
- [ ] 10 tests pass under `pytest -m "unit or integration" tests/test_context.py`.
- [ ] No real network in tests (Qdrant calls mocked via `respx` or `pytest-mock`; LLM call in compactor patched).
- [ ] `mypy --strict app/context/` passes (best-effort; known external stubs gaps documented in a comment).
