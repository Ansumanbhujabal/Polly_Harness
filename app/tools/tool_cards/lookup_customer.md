# Tool: lookup_customer

**Layer:** L3 — Tool Interfaces

Retrieve a customer record from the CRM by `customer_id` or `email`. When both identifiers are supplied, `customer_id` takes precedence. Email matching is case-insensitive to tolerate capitalisation differences in customer input. The tool returns the full `Customer` Pydantic model on a successful match, or `None` when no record is found — it never raises; the caller decides whether a missing customer constitutes an error.

**Inputs:** `customer_id: str | None`, `email: str | None` (at least one required)
**Output:** `{customer: Customer | None}`
**Failure modes:** Returns `{customer: None}` for an unknown identifier; raises `ValueError` if neither identifier is supplied at the Pydantic validation layer.
**Emits:** `L3_TOOLS / tool_invoked` with `{found, lookup_by}`.
