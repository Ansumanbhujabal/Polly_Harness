# Single-image deploy target for Hugging Face Spaces (Docker SDK).
# Runs FastAPI + Gradio + embedded Qdrant in one container. Listens on 7860 (HF default).

FROM python:3.11-slim AS base

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

# uv (fast dependency manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    PORT=7860 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -e .

# Copy source
COPY . .

# Pre-seed Qdrant collection on container start (idempotent)
EXPOSE 7860

# Healthcheck: FastAPI mounted under Gradio exposes /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:7860/healthz || exit 1

CMD ["python", "-m", "app.main"]
