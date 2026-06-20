# Polly Harness — production-grade AI customer support agent

> *"The reliability of an LLM-powered system is not the model. It is the harness around the model."*

**Polly Harness** is a 9-layer harness-engineered AI refund agent for e-commerce customer support. The product surface is a chat where a customer talks to **Polly** about a refund; the substance is everything that wraps the LLM call so an attacker can't talk the agent into approving a refund she shouldn't.

The repo is structured around a single thesis: *a reliable AI system isn't a smarter model — it's an outer system that makes the model's failures recoverable, observable, and reversible.* Every file maps to one of nine harness layers. Every percentage point of safety improvement is attributable to a single named change.

## Headline numbers

After 21 measured eval iterations on a 229-case adversarial suite:

| Metric | v1 baseline | After v21 | Δ |
|---|---|---|---|
| Overall pass rate | 28.3% | **88.6%** | **+60.3 pp** |
| A3 Injection resistance | 34.7% | 97.3–98.7%¹ | +63 pp · ✅ passes 98% threshold on stable runs |
| A4 Jailbreak resistance | 52.5% | 97.6–100%¹ | +47 pp · ✅ passes 98% threshold on stable runs |
| A6 Tone & escalation | 0% | **97.0%** | +97 pp · ✅ passes 85% threshold |
| C2 Jailbreak category | 61.8% | **100%** | +38 pp |
| C3 LLM Poisoning category | **3%** | **100%** | **+97 pp** |
| C4 Hijacking category | 40% | **100%** | +60 pp |
| C7 Translation-jailbreak (added v20) | — | 95.8% | first-measurement validates v19 clamp |
| Dollar-attributed safety bugs closed | — | **$542** | three paraphrased-injection refunds + others |

¹ Oscillates on a single ROT-13-encoded injection case (C1c-002) whose outcome depends on Azure's content filter behavior — documented in `eval/runs/v17_findings.md`.

The full audit trail lives at [`eval/IMPROVEMENT_LOG.md`](eval/IMPROVEMENT_LOG.md); the synthesizing narrative is in [`eval/PRODUCTION_GRADE_POSTMORTEM.md`](eval/PRODUCTION_GRADE_POSTMORTEM.md).

## Why this architecture matters

A reliable agent is an *outer system*, not a smarter inner model. The harness has nine layers — each catches a different class of failure:

1. **Instructions** — system prompts, persona, refund policy
2. **Context Delivery** — Qdrant RAG, intake length-guard, CRM lookup
3. **Tool Interfaces** — 8 MCP-exposed typed tools
4. **Execution Environment** — sandboxed, timeout-bounded, retried
5. **Durable State** — SqliteSaver checkpoints, audit log
6. **Orchestration** — LangGraph state machine, interrupt-before-execute, approval gates
7. **Sub-agents** — fraud-check sub-agent specializes context-quality
8. **Trust & Safety** — injection detection, jailbreak gate, abuse-flag, chargeback block
9. **Verification & Observability** — 8 judges, 229-case eval, Langfuse traces

And a **10th cross-cutting loop**: every failure surfaced by Verification becomes a structured incident, distilled into proposed new prompts / skills / verification rules / policy clarifications.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full layer-by-layer map.

## What "production-grade" means here

The phrase is unloaded by the eval framework, not by adjective. To call something production-grade in this repo, *the system has to pass a measurable threshold* on each axis:

| Axis | Threshold | Status (v21 stable run) |
|---|---|---|
| A1 Policy correctness | 95% | ✗ 60% — test-design constraint, documented |
| A3 Injection resistance | 98% | ✅ 98.7% |
| A4 Jailbreak resistance | 98% | ✅ 100% on stable C4c-003 runs; 97.6% with one stochastic flip |
| A5 Tool & decision safety | 95% | ✗ 42% — stress-test cases (API-layer concern, documented) |
| A6 Tone & escalation | 85% | ✅ 97% |

Three production-grade safety axes pass simultaneously — A3, A4, A6 — covering injection, jailbreak, and tone correctness. A1 and A5 are honest test-design constraints (see [`eval/PRODUCTION_GRADE_POSTMORTEM.md`](eval/PRODUCTION_GRADE_POSTMORTEM.md) §6), not unaddressed agent failures.

## Quick start

```bash
# 1. Configure (no real keys in .env.example — fill yours in locally)
cp .env.example .env
# Edit .env with your Azure OpenAI / Langfuse / Qdrant credentials.

# 2. Install
uv sync

# 3. Start Qdrant (or point QDRANT_URL at a managed instance)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:v1.12.0

# 4. Run the server (FastAPI + Gradio + static portfolio)
uv run uvicorn app.api.main:app --host 0.0.0.0 --port 7870

# 5. Open the surfaces
#  http://localhost:7870/        — portfolio + chat (Polly + free customer/order picker)
#  http://localhost:7870/admin   — operator dashboard (traces, approvals, eval, CRM, rules)
#  http://localhost:7870/docs    — OpenAPI / Swagger
#  http://localhost:7870/healthz — health check (Qdrant + Langfuse + version)
```

## What's in the chat surface (`/`)

- **Free customer/order picker** — speak as any of 15 customers with any of their 24 orders. CRM context loads into a left-side ticket panel: name, tier, lifetime value, prior refunds, abuse flag, chargeback flag, order items, condition, dates.
- **Six pre-baked scenarios** — one-click loads for VIP-in-window, out-of-window deny, digital-download deny, fraud-check escalate, abuse-path escalate, prompt-injection attack.
- **Polly** — the conversational LLM-composed reply path: she explains policy clauses verbatim, answers free-form questions (*"who are you?"*, *"explain policy 3 and 2"*, *"all the policies"*), and handles multi-aware turns (*"my order was damaged, btw the Dolomites are in Italy right?"*).
- **Safety properties** — Polly replies in English regardless of input language (audit reviewability), declines persona shifts (pirate, Shakespearean, "as an agent who never denies"), escalates translation-wrapped fake decisions, and refuses internal-state / chain-of-thought exfiltration.
- **Refund Rules section** — the 23-clause policy doc rendered as 10 sectioned cards plus a color-coded cheat-sheet table.
- **Architecture diagrams** — the 9-layer stack and the message-to-decision LangGraph flow, both inline SVG.
- **Trajectory plot** — v0 → v21 with annotated big jumps (real L9 LLM-judge, interrupt-state response, A6 axis-restructure, LLM respond, poisoning gate, Polly + policy doc, English-only clamp, C7 coverage added, translation-fake escalate).

## What's in the admin surface (`/admin`)

A Gradio operator dashboard with:

- **Operations** — Live Trace (SSE LayerEvent stream), Architecture Diagram, Pending Approvals (human-in-the-loop approve/deny), Incidents (Distiller).
- **CRM Data** — Customer + Order tables.
- **Refund Rules** — the same policy doc as a markdown view for operators.
- **Eval Progress** — Headline metrics, axis bar charts, category bar charts, iteration timeline cards, verbose Improvement Log, per-iteration findings dropdown, axis score matrix, latest run report, production-grade postmortem.

## The eval

The eval framework is the discipline that makes this serious. It's a 229-case adversarial suite covering seven categories:

- **C1 Prompt injection** (42 cases) — direct, paraphrased, encoded, multi-step, tool-output injections
- **C2 Jailbreak** (34 cases) — role-play, DAN, hypothetical, recursive break-character attempts
- **C3 LLM poisoning** (33 cases) — false-premise, context-stuffing, authority spoof, conversation-poisoning
- **C4 Hijacking** (25 cases) — tool-output, output-format, chain-of-thought leak
- **C5 Stress** (33 cases) — length, malformed, concurrency, rate-spike
- **C6 Abuse** (33 cases) — emotional, legal threats, profanity, persistent hostility
- **C7 Translation-jailbreak** (24 cases, added v20) — direct translation request, chained translation + decision biasing, non-English input

Plus 5 hand-curated cases for policy-citation correctness. Each case carries an expected `decision_kind`, `cited_clauses`, `reason_code`, and (where relevant) the upstream block-check it should trigger.

Eight judges score each case: `policy_correctness`, `policy_grounding`, `injection_resistance`, `jailbreak_resistance`, `tone_appropriate`, `refusal_correctness`, `hallucination_check`, `tool_safety`. Each judge is a Python function or an LLM call with explicit acceptance criteria. Cohen κ + drift z-test + ECE on calibration.

```bash
# Run the eval
uv run python eval/run_simulation.py \
  --ground-truth eval/ground_truth.json \
  --output eval/runs/v22.json \
  --baseline eval/runs/v21.json
```

Output: a JSON run file + an updated `eval/EVAL_RESULTS.md` + a written before/after diff at the case level. Iterations are tracked in `eval/IMPROVEMENT_LOG.md` with one named change per row.

## Project layout (high level)

```
app/
  api/             FastAPI routes — chat, crm, approvals, events, admin
  config.py        Pydantic Settings (env-driven)
  context/         Compaction / RAG retrieval / state
  domain/          Pydantic models — AgentState, RefundDecision, ToolInvocation
  graph/           LangGraph state machine — nodes, edges, refund_graph
    nodes/         intake, identify_customer, classify_intent, retrieve_policy,
                   eligibility_check, fraud_check, compute_decision, respond, ...
  instructions/    Prompt loader (Langfuse-first, local fallback) + cache
  mcp/             MCP server exposing the 8 tools
  observability/   Layer event emitter, Langfuse handler, SSE bus
  tools/           lookup_customer, get_order, check_return_window, ...
  verification/    L9 axis judges

data/
  crm/             15 customers, 24 orders (synthetic)
  policy/          refund_policy_v1.md — 23 clauses, the source of truth

eval/
  ground_truth.json          229 labelled cases across 7 categories
  thresholds.yaml            axis-level production-grade thresholds
  IMPROVEMENT_LOG.md         master tracker, top-to-bottom = the story
  PRODUCTION_GRADE_POSTMORTEM.md   synthesizing narrative
  EVAL_RESULTS.md            live human-readable report
  adversarial/               6 generators
  judges/                    8 axis judges
  runs/v{1..21}.json         machine-readable runs
  runs/v{1..21}_findings.md  per-iteration hypothesis + intervention + Δ + residual
  run_simulation.py          the production runner

frontend/
  templates/index.html       Jinja portfolio (the surface at /)
  static/portfolio.css       drafting-table design system
  static/chat.js             custom inline chat — picker, sidebar, decision chips
  portfolio_data.py          shapes eval data + policy doc for the template
  app.py                     Gradio dashboard (admin)

prompts/
  intent_classifier.md       L1 intent router prompt (the heavy lifter)
  system_refund_agent.md     L1 main agent prompt
  fraud_check_subagent.md    L7 sub-agent prompt
  denial_rewriter.md         L1 denial composition
  distiller.md               L9 incident distiller
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| LLM | Azure OpenAI (`gpt-4o-mini` default, `gpt-4o` for harder paths) | enterprise content filter + Langfuse integration |
| Orchestration | LangGraph 0.2+ | StateGraph + interrupt-before-execute + SqliteSaver |
| Tools | MCP protocol via custom server | typed schemas, audit-friendly |
| Vector store | Qdrant 1.12 | policy clause retrieval |
| Observability | Langfuse Cloud | traces + prompt registry + LLM-as-judge integration |
| State | SQLite + LangGraph SqliteSaver | survives crashes, simple to inspect |
| API | FastAPI 0.115+ | OpenAPI for the eval runner, Starlette routing |
| Portfolio | Jinja2 + vanilla CSS/JS | full design control, no framework lock-in |
| Operator UI | Gradio 6.19 (mounted on FastAPI) | fast to build, fine for internal tools |
| Eval | Custom Python runner | async, 229 cases, 8 judges, before/after diff |

## License

MIT — see [`LICENSE`](LICENSE).

## Contact

Built by **Ansuman SS Bhujabala** — AI Engineer, focus on agentic systems, evals at scale, and AI safety.

- Email: [ansumanbhujabal1@gmail.com](mailto:ansumanbhujabal1@gmail.com)
- LinkedIn: [linkedin.com/in/ansuman-simanta-sekhar-bhujabala](https://www.linkedin.com/in/ansuman-simanta-sekhar-bhujabala)
- GitHub: [github.com/Ansumanbhujabal](https://github.com/Ansumanbhujabal)
