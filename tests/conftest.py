"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.domain.models import Customer, Order


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def raw_customers(repo_root: Path) -> dict:
    return json.loads((repo_root / "data" / "crm" / "customers.json").read_text())


@pytest.fixture(scope="session")
def raw_orders(repo_root: Path) -> dict:
    return json.loads((repo_root / "data" / "crm" / "orders.json").read_text())


@pytest.fixture
def all_customers(raw_customers: dict) -> list[Customer]:
    return [Customer(**c) for c in raw_customers["customers"]]


@pytest.fixture
def all_orders(raw_orders: dict) -> list[Order]:
    return [Order(**o) for o in raw_orders["orders"]]


@pytest.fixture
def vip_customer(all_customers: list[Customer]) -> Customer:
    return next(c for c in all_customers if c.customer_id == "CUST-001")


@pytest.fixture
def serial_refunder(all_customers: list[Customer]) -> Customer:
    return next(c for c in all_customers if c.customer_id == "CUST-004")


@pytest.fixture
def chargeback_customer(all_customers: list[Customer]) -> Customer:
    return next(c for c in all_customers if c.customer_id == "CUST-005")


@pytest.fixture
def policy_doc_text(repo_root: Path) -> str:
    return (repo_root / "data" / "policy" / "refund_policy_v1.md").read_text()


@pytest.fixture(autouse=True)
def _isolated_sqlite_path(tmp_path, monkeypatch):
    """Every test gets its own SQLite file so durable state tests don't collide."""
    db = tmp_path / "test_state.db"
    monkeypatch.setenv("SQLITE_PATH", str(db))
    # Refresh module-level settings cache if needed
    monkeypatch.setattr(settings, "SQLITE_PATH", str(db), raising=False)
    yield
