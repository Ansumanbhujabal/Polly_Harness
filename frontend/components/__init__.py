"""Frontend component factories."""

from frontend.components.admin_panel import admin_panel_factory
from frontend.components.approval_panel import approval_panel_factory
from frontend.components.chat_panel import chat_panel_factory
from frontend.components.incidents_panel import incidents_panel_factory

__all__ = [
    "admin_panel_factory",
    "approval_panel_factory",
    "chat_panel_factory",
    "incidents_panel_factory",
]
