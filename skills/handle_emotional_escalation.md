---
id: handle_emotional_escalation
name: Handle Emotional Escalation
intents: [complaint, frustrated, legal_threat]
triggers_on: []
description: When a customer is angry, distressed, or threatening legal action, de-escalate first before engaging with any factual dispute or policy recitation. Acknowledge the feeling, restate what you can do, and offer a human escalation path.
priority: 5
---

## When to use

Use this skill whenever the classified intent is `complaint`, `frustrated`, or `legal_threat`. These three intents share a common pattern: the customer is no longer in a calm transactional mindset. Before any policy clause can land, the emotional charge must be addressed. Jumping straight to policy citations when a customer is in distress reads as robotic and often inflames rather than calms.

A `legal_threat` intent ("I'll sue you", "my lawyer will contact you") is a special case — it requires acknowledging the seriousness of the situation without either validating the legal merits of the threat or dismissing the customer's frustration. Escalation to a senior agent or legal-aware handler should be offered promptly.

This skill has no `triggers_on` predicates because emotional escalation is always-active for these intents — it does not depend on whether the customer is identified or what the candidate decision is.

## The pattern

1. **Lead with acknowledgment, not facts.** The first sentence must validate what the customer is feeling, not explain policy. "I can hear how frustrating this has been" outperforms "per our policy, returns are accepted within 14 days" as an opening when the customer is upset.
2. **Do not argue about facts in the first response.** Even if the customer's account of events is factually inaccurate, the first response is not the place to correct it. Correct once they are calm.
3. **Name one concrete thing you will do.** Vague promises ("I'll look into it") increase anxiety. Name the specific next action: "I'm pulling up your order right now" or "I'm routing this to a senior agent who handles these situations."
4. **Offer human escalation unprompted for legal threats.** Do not wait for the customer to ask. Say explicitly: "This sounds like something our senior support team should handle — would you like me to connect you?"
5. **Restate policy only after the emotional charge has dropped.** If the conversation continues past the first exchange, policy can be cited once the customer signals they are ready to engage with specifics.
6. **Close with agency.** The customer should feel they have a clear path forward, not that they've hit a wall.

## Pitfalls

- **Policy-first responses.** Starting with "According to POLICY-001..." when a customer is furious will escalate the situation, not resolve it.
- **Dismissing the threat.** Responding to "I'll sue you" with "that's not how refunds work" is adversarial. Acknowledge the seriousness; offer a human.
- **Over-promising.** "We'll fix this right away" without a specific action creates expectation mismatches. Be specific.
- **Repeating the same de-escalation phrase.** If the customer remains agitated after the first acknowledgment, do not repeat the same line. Vary the response and escalate the offer of a human agent.
- **Ignoring the underlying request.** De-escalation is not a substitute for resolving the refund. Once the tone has stabilized, return to the actual issue and process it.
