---
id: explain_denial_with_alternative
name: Explain Denial With Alternative
intents: [refund_request]
triggers_on: ["candidate_decision.kind == deny"]
description: When the candidate decision is a denial, lead with empathy, cite the specific policy clause that governs the denial, then propose a concrete alternative such as store credit or an exchange.
priority: 0
---

## When to use

Use this skill whenever the eligibility check and policy engine have produced a candidate decision of `deny`. A denial is the highest-friction outcome in the refund workflow — the customer is expecting money back and will receive neither a refund nor store credit by default. How this is communicated directly determines whether the customer churns or remains.

This skill activates specifically on `candidate_decision.kind == deny`. It does not activate for partial approvals, store-credit approvals, or escalations — those have their own patterns. The denial case is uniquely sensitive because the customer typically believes they are in the right.

Common denial scenarios: item returned outside the 14-day (or 60-day VIP) window; item opened and used with no defect reported; customer flagged for refund abuse; digital goods past the 48-hour download window; items in the "Final Sale" category.

## The pattern

1. **Open with empathy — one sentence, genuine.** "I'm sorry this wasn't the experience you were hoping for" or "I understand this is disappointing." Keep it brief; extended empathy reads as stalling.
2. **State what the system found, not what the customer did wrong.** Frame the denial around the policy condition, not a personal accusation. "The return window for this order closed on [date]" rather than "You waited too long."
3. **Cite the specific policy clause by ID.** Reference the clause (e.g., POLICY-001, POLICY-008) so the customer knows this is not an agent discretion call. This reduces re-negotiation attempts directed at "getting a different agent."
4. **Propose a concrete alternative immediately after the denial.** Never leave the conversation on a hard "no." If store credit is available (POLICY-003), name the amount. If exchange is possible, offer it. If the customer is VIP, note the extended window for future orders.
5. **Explain what would have changed the outcome.** One sentence: "If the return request had been received before [date], a full refund would have been processed." This is informational — it helps the customer understand the system without being preachy.
6. **Invite questions.** Close with an open door: "Is there anything else I can clarify about this decision?" This signals the conversation is not closed and the customer has not been abandoned.

## Pitfalls

- **Delivering the denial without an alternative.** A plain "we cannot process your refund" with no next step is a churn driver. Always offer store credit or exchange unless they are also explicitly excluded by policy.
- **Citing policy before empathy.** The sequence matters. Empathy → policy → alternative. Reversing the order makes the empathy feel performative.
- **Over-explaining the policy.** One clause citation is sufficient. Listing every sub-clause reads as defensive and increases customer frustration.
- **Hiding behind policy language.** "The terms and conditions clearly state..." is adversarial phrasing. Use plain language: "Our return window is 14 days, and this order is past that."
- **Skipping the alternative if stock is unavailable.** If exchange inventory is unavailable, say so and offer what is available — even a goodwill discount code is better than a hard no with no alternative.
- **Allowing the denial to read as punitive.** The customer should leave understanding that the denial is a rules-based outcome, not a judgment about them as a person.
