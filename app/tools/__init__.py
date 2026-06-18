"""L3 Tools layer — public interface.

Exports:
  TOOLS: list[BaseTool] — all 8 tools with default (file-based) data sources.
  get_tool_by_name: fast lookup by tool name.
  BaseTool: base class for tool authoring.

The TOOLS list is used by:
  - The MCP server (app/mcp/server.py) to register tools with the protocol.
  - LangGraph nodes to call tools by name.

Tool data sources (CRM customers/orders) are loaded once at import time from
the paths in settings. For test isolation, inject data directly via the tool
constructors (e.g. LookupCustomer(customers=[...])).
"""

from __future__ import annotations

import json

from app.config import settings
from app.domain.models import Customer, Order
from app.tools.base import BaseTool
from app.tools.customer_tools import LookupCustomer
from app.tools.executor import run_tool
from app.tools.order_tools import GetOrder
from app.tools.policy_tools import (
    CheckItemCondition,
    CheckReturnWindow,
    ComputeRefundAmount,
    SearchPolicy,
)
from app.tools.refund_tools import EscalateToHuman, IssueRefund


def _load_customers() -> list[Customer]:
    data = json.loads(settings.CUSTOMERS_PATH.read_text())
    return [Customer(**c) for c in data["customers"]]


def _load_orders() -> list[Order]:
    data = json.loads(settings.ORDERS_PATH.read_text())
    return [Order(**o) for o in data["orders"]]


def _build_tools() -> list[BaseTool]:
    customers = _load_customers()
    orders = _load_orders()
    return [
        LookupCustomer(customers=customers),
        GetOrder(orders=orders),
        CheckReturnWindow(),
        CheckItemCondition(),
        ComputeRefundAmount(),
        IssueRefund(),
        EscalateToHuman(),
        SearchPolicy(),
    ]


TOOLS: list[BaseTool] = _build_tools()

_TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in TOOLS}


def get_tool_by_name(name: str) -> BaseTool | None:
    """Return the tool with the given name, or None if not found."""
    return _TOOL_MAP.get(name)


__all__ = ["TOOLS", "get_tool_by_name", "BaseTool", "run_tool"]
