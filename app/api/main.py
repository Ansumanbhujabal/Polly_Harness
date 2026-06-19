"""FastAPI application factory.

Entry point for uvicorn:
    uvicorn app.api.main:app

The Gradio frontend mounts at root once E1 lands:
    # TODO(E1): uncomment after frontend.app.build_gradio_app exists
    # import gradio as gr
    # from frontend.app import build_gradio_app
    # gr.mount_gradio_app(app, build_gradio_app(), path="/")
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.lifespan import lifespan
from app.api.routes import router
from app.config import settings

app = FastAPI(
    title="Refund Harness API",
    version="0.1.0",
    description="Harness-engineered AI customer support agent for refund processing.",
    lifespan=lifespan,
)

# CORS — single-user demo; origins come from settings (ADR-0006)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# ---------------------------------------------------------------------------
# TODO(E1): Mount Gradio after the frontend layer lands.
# ---------------------------------------------------------------------------
# import gradio as gr
# from frontend.app import build_gradio_app
# gr.mount_gradio_app(app, build_gradio_app(), path="/")
