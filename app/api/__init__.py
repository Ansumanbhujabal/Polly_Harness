"""app.api — FastAPI application.

Public contract:
    from app.api import app   # FastAPI ASGI app, used by uvicorn
    from app.api.main import app  # equivalent
"""

from app.api.main import app

__all__ = ["app"]
