# ADR-0006: Authentication / Authorization Deferred to Production

**Status:** Accepted
**Date:** 2026-06-18

## Context

The v0.1 release is a single-user demo on Hugging Face Spaces. The deployed `*.hf.space` URL is publicly reachable but there is one "agent" and one "customer" in the live demo at a time. Adding real auth (FastAPI middleware + tenant scoping + identity provider integration) would consume implementation time without changing what the walkthrough shows.

## Decision

**No authentication on any endpoint** in the v0.1 deployed surface. CORS allows `localhost:7860` by default (configurable via `settings.CORS_ALLOWED_ORIGINS`). The decision is documented here AND in the README's scope-cut section so a reviewer never mistakes the absence of auth for an oversight.

The shape we'd take in production is documented for clarity:
- A FastAPI `Depends(get_current_user)` dependency injected on every `/api/v1/*` route, backed by an identity provider (Azure AD / Okta / Clerk).
- Tenant scoping in `app.state.Repository` — every `save_refund` / `find_refund` / `list_pending_approvals` query includes `tenant_id` as a filter.
- A separate `/admin/*` route group gated by role check (`admin` / `support_lead`).

## Consequences

**Why deferring is the right call here:**
- The point of v0.1 is not to demonstrate that `passlib` and `python-jose` can be wired — it's to show what production scaffolding would look like, and where the seams are.
- The Repository facade is already the seam — `tenant_id` would be added there with one column on each table and one filter on each query. The change is small *because* the architecture anticipated it.

**What we gave up:** An end-to-end "production-ready" claim that the walkthrough could close on. The honest claim instead: "production-grade for a single-tenant single-user demo, with an explicit named seam for multi-tenant."

**Verification:** No `Depends` of auth shape exists in `app/api/routes/`. README lists "No authentication / authorization" under scope cuts. The Repository's method signatures take `conversation_id` (not `tenant_id`), making the missing column visible to a future reader.
