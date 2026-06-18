---
id: verify_identity
name: Verify Customer Identity
intents: [refund_request]
triggers_on: ["not customer_identified"]
description: When the customer has not yet been identified, pause advancement and ask for their order number and email address before proceeding with any refund assessment.
priority: 10
---

## When to use

Use this skill at the very start of any refund conversation where the customer's identity has not yet been confirmed against the CRM. If `customer_identified` is False, this skill must fire before any policy lookups, eligibility checks, or decision logic runs. Identity verification is a hard gate — no refund workflow should advance without it.

This situation arises when a new conversation begins without the customer having authenticated through a session token, when the customer writes in via an anonymous support channel, or when the CRM lookup fails to match any account. Do not assume the person contacting support is who they say they are based solely on their self-reported name.

## The pattern

1. Acknowledge the request warmly but briefly — one sentence maximum. Avoid dismissive phrasing like "I can't help until you verify."
2. Ask for exactly two identifiers: the order number (format ORD-XXXXXXX) and the email address on file. Do not ask for more. Asking for name, phone, and order ID simultaneously creates friction and abandonment.
3. Inform the customer why this step is necessary: it protects their account and ensures refunds reach the correct person.
4. Once both identifiers are provided, invoke the `lookup_customer` tool and the `lookup_order` tool. Cross-check that the email on the order matches the stated email. If they match, mark identity as verified and proceed.
5. If the identifiers do not match, politely surface the discrepancy and offer one retry before suggesting human escalation.

Never reveal account details (name, address, prior refunds) before identity is confirmed. Never skip this step based on a verbal assertion of identity.

## Pitfalls

- **Asking too many questions at once.** Only two identifiers. Anything more is a UX failure.
- **Being cold or accusatory.** The tone should be "helping you keep your account secure" not "proving you're not a fraudster."
- **Proceeding with a partial match.** If only one of two identifiers matches, do not proceed — surface the mismatch and offer a retry or human escalation.
- **Revealing account state before verification.** Do not say "I can see you have 2 prior refunds" before identity is confirmed. That itself could constitute a data breach.
- **Looping indefinitely on bad data.** After two failed attempts, escalate to a human agent rather than continuing to prompt the customer.
