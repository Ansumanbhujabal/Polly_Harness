# Multi-stage Dockerfile for Hugging Face Spaces (Docker SDK).
# Runs FastAPI + Gradio on port 7860 (HF default).
# Final image: python:3.11-slim, non-root appuser (uid 1000), no uv, no build artifacts.

# --- builder stage ---
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# --- runtime stage ---
FROM python:3.11-slim AS runtime

# System deps needed at runtime (curl for HEALTHCHECK, ca-certs for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user (uid 1000)
RUN useradd --uid 1000 --create-home appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=7860 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

WORKDIR /app

# Copy the pre-built venv from builder — no uv, no build tools in final image
COPY --from=builder /app/.venv /app/.venv

# Copy only production paths; .git/ and tests/ are intentionally excluded
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser skills/ ./skills/
COPY --chown=appuser:appuser agentic.md ./agentic.md

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:7860/healthz || exit 1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
