# Tool: search_policy

**Layer:** L3 — Tool Interfaces

Search the refund policy document for clauses relevant to a free-text query and return the top-K most relevant `PolicyClause` objects. Each `PolicyClause` carries a stable `clause_id` (e.g. `POLICY-007`), the full clause text, and a `relevance_score`. The tool currently uses an in-memory keyword-overlap scorer that parses the policy markdown into per-clause chunks keyed on `POLICY-NNN` identifiers; this is intentionally simple and deterministic for testing. When the Context layer (SPEC_CONTEXT) is implemented in Wave 2, this tool will delegate to `app.context.retriever` for Qdrant vector search with semantic embeddings, which will significantly improve retrieval quality for paraphrased queries.

**TODO: replace in-memory keyword fallback with Qdrant vector search when SPEC_CONTEXT lands.**

**Inputs:** `query: str`, `top_k: int` (default 5, max 20)
**Output:** `{clauses: list[PolicyClause]}`
**Failure modes:** If the policy document cannot be read at init time, a `FileNotFoundError` is raised from the constructor (not the run method). An empty query returns clauses with `relevance_score=0.0` in parse order.
**Emits:** `L3_TOOLS / tool_invoked` with `{query, results, top_clause}`.
