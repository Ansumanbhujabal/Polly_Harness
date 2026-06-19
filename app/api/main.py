"""FastAPI application factory.

Mounts:
  - GET  /             custom portfolio HTML (the hero)
  - GET  /static/*     CSS + JS assets
  - GET  /admin        full Gradio dashboard (live trace, approvals, incidents, CRM, eval)
  - GET  /chat         bare Gradio chat (embedded in / via iframe)
  - GET  /docs         FastAPI OpenAPI browser
  - All /api/*, /events/*, /healthz routes from app.api.routes
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.lifespan import lifespan
from app.api.routes import router
from app.config import settings
from frontend.app import build_chat_only_app, build_gradio_app
from frontend.portfolio_data import template_context

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = REPO_ROOT / "frontend" / "static"
TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"
EVAL_RUNS_DIR = REPO_ROOT / "eval" / "runs"
EVAL_ROOT = REPO_ROOT / "eval"

app = FastAPI(
    title="Refund Harness API",
    version="0.1.0",
    description="Harness-engineered AI customer support agent for refund processing.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def portfolio_root(request: Request) -> HTMLResponse:
    """Render the portfolio surface — hero, trajectory, evidence, embed."""
    ctx = template_context()
    return templates.TemplateResponse(request, "index.html", ctx)


_FINDINGS_WRAPPER = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><title>{title} — Refund Harness</title>
<link rel="stylesheet" href="/static/portfolio.css">
<style>
  body {{ background: var(--surface); padding: 0; }}
  .findings-shell {{ max-width: 880px; margin: 48px auto; padding: 32px 40px; background: var(--paper); border: 1px solid var(--grid); border-radius: 4px; font-family: var(--font-body); color: var(--ink); }}
  .findings-shell h1 {{ font-family: var(--font-display); font-size: 28px; margin-top: 0; color: var(--blueprint); letter-spacing: -0.01em; }}
  .findings-shell h2 {{ font-family: var(--font-display); font-size: 19px; margin-top: 24px; color: var(--ink); border-bottom: 1px solid var(--grid); padding-bottom: 6px; }}
  .findings-shell h3 {{ font-family: var(--font-display); font-size: 15px; margin-top: 18px; color: var(--ink-2); }}
  .findings-shell code, .findings-shell pre {{ font-family: var(--font-mono); background: var(--surface); padding: 2px 6px; border-radius: 2px; font-size: 12.5px; }}
  .findings-shell pre {{ padding: 12px 16px; overflow-x: auto; border: 1px solid var(--grid); }}
  .findings-shell blockquote {{ border-left: 3px solid var(--blueprint); padding: 4px 14px; color: var(--ink-2); margin: 12px 0; background: var(--surface); }}
  .findings-shell table {{ border-collapse: collapse; margin: 14px 0; font-size: 13px; }}
  .findings-shell th, .findings-shell td {{ border: 1px solid var(--grid); padding: 6px 10px; text-align: left; }}
  .findings-shell th {{ background: var(--surface); font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.04em; }}
  .findings-shell a {{ color: var(--blueprint); }}
  .findings-shell .topnav {{ font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; color: var(--ink-3); margin-bottom: 24px; }}
  .findings-shell .topnav a {{ margin-right: 14px; }}
</style></head><body><div class="findings-shell">
<div class="topnav"><a href="/">← portfolio</a><a href="/admin">/admin</a><a href="/eval/findings/index">all iterations</a></div>
{body}
</div></body></html>"""


def _render_md_file(path: Path, title: str) -> HTMLResponse:
    if not path.exists():
        return HTMLResponse(
            _FINDINGS_WRAPPER.format(title="not found", body=f"<h1>404 — {path.name}</h1><p>This findings doc does not exist on disk.</p>"),
            status_code=404,
        )
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True}).enable("table")
        body_html = md.render(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        body_html = f"<pre>{path.read_text(encoding='utf-8')}</pre>"
    return HTMLResponse(_FINDINGS_WRAPPER.format(title=title, body=body_html))


@app.get("/eval/findings/{version}", response_class=HTMLResponse, include_in_schema=False)
async def get_findings(version: str) -> HTMLResponse:
    """Render eval/runs/vN_findings.md as styled HTML."""
    safe = version.replace("/", "").replace("\\", "").strip()
    return _render_md_file(EVAL_RUNS_DIR / f"{safe}_findings.md", f"{safe} findings")


@app.get("/eval/findings/index", response_class=HTMLResponse, include_in_schema=False)
async def get_findings_index() -> HTMLResponse:
    """Index of every findings doc — quick jump-to for the eval narrative."""
    items: list[str] = []
    for p in sorted(EVAL_RUNS_DIR.glob("v*_findings.md")):
        v = p.stem.replace("_findings", "")
        try:
            num = int(v[1:])
        except ValueError:
            num = 999
        items.append((num, v, p.name))
    items.sort()
    rows = "".join(
        f"<li><a href='/eval/findings/{v}'>{v}</a> — {name}</li>"
        for _, v, name in items
    )
    return _render_md_file(EVAL_ROOT / "IMPROVEMENT_LOG.md", "improvement log")  # fallback


@app.get("/eval/improvement_log", response_class=HTMLResponse, include_in_schema=False)
async def get_improvement_log() -> HTMLResponse:
    return _render_md_file(EVAL_ROOT / "IMPROVEMENT_LOG.md", "improvement log")


@app.get("/eval/postmortem", response_class=HTMLResponse, include_in_schema=False)
async def get_postmortem() -> HTMLResponse:
    return _render_md_file(EVAL_ROOT / "PRODUCTION_GRADE_POSTMORTEM.md", "production-grade postmortem")


# All FastAPI API routes (/healthz, /api/v1/*, /events/*, /admin/api/*, etc.)
app.include_router(router)

# Gradio mounts last — they own /admin and /chat paths
app = gr.mount_gradio_app(app, build_chat_only_app(), path="/chat")
app = gr.mount_gradio_app(app, build_gradio_app(), path="/admin")
