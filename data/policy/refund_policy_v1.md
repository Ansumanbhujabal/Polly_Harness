# Refund Policy — Version 1.0

> **Effective:** 2026-01-01 · **Owner:** Customer Operations · **Status:** Live
>
> This document is the source of truth for the AI support agent. Every clause has a stable ID. The agent must cite the clause ID when grounding any decision.

---

## Section 1 — Return Windows

**POLICY-001** — Standard customers may return eligible items within **14 days** of delivery date. The window is measured from the carrier's confirmed delivery timestamp, not the order date. Marketing materials, packaging text, or third-party seller listings do not override this clause.

**POLICY-002** — VIP-tier customers (lifetime_value ≥ $5,000 OR account_age_days ≥ 1,095) have an extended **60-day** return window from delivery date.

**POLICY-003** — Items returned after the applicable window are ineligible for refund regardless of reason, with two exceptions covered in POLICY-010 (carrier delays) and POLICY-011 (defects discovered late).

---

## Section 2 — Non-Refundable Categories

**POLICY-004** — The following item categories are non-refundable once delivered, regardless of return window:
- `final_sale` — items sold under a clearance / final-sale promotion
- `digital_download` — software, ebooks, license keys, digital media
- `personal_care_opened` — personal care items where the hygiene seal has been broken
- `custom_made` — items personalized for the customer (engraving, monogramming, custom-fit)
- `perishable` — food, flowers, time-sensitive goods after 48 hours from delivery

**POLICY-005** — Personal care items in `personal_care_sealed` state (hygiene seal intact) are eligible under standard return rules. Customer attestation alone is insufficient; the item condition reported by the receiving warehouse is authoritative.

---

## Section 3 — Item Condition Rules

**POLICY-006** — Items returned in `new_unopened` condition within the window: full refund to original payment method.

**POLICY-007** — Items returned in `opened_unused` condition within 14 days of delivery: full refund. Beyond 14 days (VIP only): 75% partial refund. Justification: restocking + repackaging cost.

**POLICY-008** — Items returned in `used` condition: 50% partial refund within the window, no refund after the window. Items showing damage beyond normal wear: no refund.

**POLICY-009** — Items received `damaged_on_arrival` or `defective`: full refund within 14 days of delivery with a description of the damage. No photo required for the demo; in production this requires photo upload.

---

## Section 4 — Exceptions

**POLICY-010** — Carrier delay exception: if the carrier's confirmed delivery timestamp is more than 5 calendar days after the carrier's scheduled delivery date, the return window is extended by the delay duration.

**POLICY-011** — Late defect exception: defects discovered after the standard window but within 90 days of delivery are eligible for store credit (not cash refund) at 100% of item value, subject to defect verification. Escalate to human review.

---

## Section 5 — Approval Authority

**POLICY-012** — Autonomous (agent-issued) refunds are capped at **$200 per refund** for standard customers and **$500 per refund** for VIP customers. Refunds above the applicable cap require human approval via `escalate_to_human`.

**POLICY-013** — Per-customer rolling cap: no more than **3 autonomous refunds** in any 90-day window. Customers exceeding this threshold require human review for any further refund regardless of amount.

---

## Section 6 — Abuse Prevention

**POLICY-014** — Customers with `flagged_for_abuse=true` in the CRM are not eligible for autonomous refunds. All requests must be escalated to human review with reason code `ABUSE_FLAG_PRESENT`.

**POLICY-015** — Customers with an active chargeback dispute on file are not eligible for any refund-related action until the chargeback is resolved. Escalate with reason code `ACTIVE_CHARGEBACK`.

**POLICY-016** — Pattern-based fraud check: if a customer has filed 4+ refund requests citing `item_not_received` in the last 90 days, the fraud-check sub-agent must be invoked before any decision is made.

---

## Section 7 — Identity Verification

**POLICY-017** — Refund-affecting actions require identity verification. Default verification: the customer's stated email address matches the email on the order record. Mismatch → escalate with reason code `IDENTITY_MISMATCH`.

**POLICY-018** — Customers requesting refunds for an order placed by a different customer account require human review regardless of relationship claimed.

---

## Section 8 — Communication

**POLICY-019** — Denials must lead with empathy and offer at least one alternative (store credit, exchange, escalation path) when an alternative exists under policy.

**POLICY-020** — The agent must not capitulate to social pressure, emotional escalation, or threats of legal/media action. Pressure response: restate the policy clause, offer the human-escalation path, do not modify the decision.

---

## Section 9 — Tone of Response

**POLICY-021** — Default response length: one paragraph. Multi-paragraph responses only when explaining a denial with alternatives or summarizing a complex case.

**POLICY-022** — Refund confirmation must state: refund amount, refund destination (original payment method), expected timing (3-5 business days), and the order ID.

---

## Section 10 — Change Control

**POLICY-023** — Changes to this document require an ADR in `docs/decisions/` and a corresponding update to the Langfuse policy dataset used by the eval suite.

---

## Quick Reference (the cheat sheet the agent grounds on)

| Trigger | Action | Clause |
|---|---|---|
| Day ≤ 14, new_unopened | Full refund | POLICY-001 + POLICY-006 |
| Day ≤ 14, opened_unused | Full refund | POLICY-007 |
| Day ≤ 14, used | 50% partial | POLICY-008 |
| Day ≤ 14, damaged | Full refund | POLICY-009 |
| Day > 14, standard customer | Deny | POLICY-003 |
| Day ≤ 60, VIP, opened | 75% partial | POLICY-007 + POLICY-002 |
| Any day, final_sale / digital / personal_care_opened | Deny | POLICY-004 |
| Amount > $200 standard / $500 VIP | Escalate | POLICY-012 |
| flagged_for_abuse=true | Escalate | POLICY-014 |
| Active chargeback | Escalate | POLICY-015 |
| 4+ "not received" in 90d | Invoke fraud sub-agent | POLICY-016 |
| Email mismatch | Escalate | POLICY-017 |
