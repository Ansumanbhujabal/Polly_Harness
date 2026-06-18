"""customer_context_builder — L2 Context: PII redaction + minimal customer snapshot.

Produces a small dict ready for prompt-injection. The raw Customer and Order
objects are never leaked outside this module — only the projected, redacted dict
is returned.

PII redaction rules
-------------------
- email : keep first char of local-part, replace rest with ``***``, keep domain.
          e.g. ``jane.doe@example.com`` → ``j***@example.com``
- phone : keep last 4 chars of the raw string, prefix with ``***-``.
          e.g. ``+91-98765-43210`` → ``***-3210``
          If phone is absent or shorter than 4 chars → ``***``
"""

from __future__ import annotations

from typing import Any

from app.domain.models import Customer, Order


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _redact_email(email: str) -> str:
    """Redact all but the first character of the email local-part."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _redact_phone(phone: str) -> str:
    """Keep only the last 4 digits, prefix with ``***-``."""
    if not phone or len(phone) < 4:
        return "***"
    return f"***-{phone[-4:]}"


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def build_customer_context(customer: Customer, order: Order | None) -> dict[str, Any]:
    """Return a minimal, PII-redacted dict suitable for prompt injection.

    Parameters
    ----------
    customer:
        The resolved Customer object from CRM.
    order:
        The resolved Order, or ``None`` if no order has been identified yet.

    Returns
    -------
    dict with redacted customer info and (optionally) compact order summary.
    No order keys are present when ``order`` is ``None``.
    """
    ctx: dict[str, Any] = {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "email": _redact_email(customer.email),
        "phone": _redact_phone(customer.phone),
        "tier": customer.tier,
        "account_age_days": customer.account_age_days,
        "lifetime_value_usd": customer.lifetime_value_usd,
        "prior_refund_count": customer.prior_refund_count,
        "prior_refunds_last_90d": customer.prior_refunds_last_90d,
        "flagged_for_abuse": customer.flagged_for_abuse,
        "active_chargeback": customer.active_chargeback,
    }

    if order is not None:
        ctx["order_id"] = order.order_id
        ctx["order_status"] = order.status
        ctx["order_total_usd"] = order.total_usd
        ctx["order_purchase_date"] = order.purchase_date
        ctx["order_delivery_date"] = order.delivery_date
        ctx["order_items"] = [item.name for item in order.items]

    return ctx
