# Spec — Human-in-the-loop (HITL)

## Purpose

The escalation boundary. Humans review the **residual** — the cases deterministic gates and high-confidence model paths already couldn't resolve — not the whole volume. HITL is switched on only after a module clears its harness bar (`docs/specs/eval-harness.md`).

## Position in pipeline

```
any module low-confidence / refusal-risk / HOLD gate / explicit request
   ──► escalation record ──► human review queue ──► resolution (approve/request-more/override)
```

## Canonical type

```jsonc
// Escalation
{
  "escalation_id": "esc_0001",
  "client_id": "c_0021",
  "trigger": "low_confidence | refusal_risk | hold_gate | form_answer_change | explicit_request",
  "source_module": "gap-analysis",
  "context": {                 // full provenance bundle for the reviewer
    "case": "…", "documents": ["doc_0001", "doc_0002"],
    "gap_report": "…", "flagged_claims": ["…"]
  },
  "state": "open | resolved",
  "resolution": null | { "action": "approve | request_more | override", "by": "human_id", "note": "…" }
}
```

## Escalation triggers

| Trigger | When |
|---|---|
| `low_confidence` | any model value below threshold (e.g. intent < 0.6, extraction confidence low) |
| `refusal_risk` | gap/assembly patterns known to risk refusal (insufficient funds, weak home ties, unclear purpose) |
| `hold_gate` | any verification gate returns `HOLD` |
| `form_answer_change` | a proposed change to a submitted form answer (high-stakes mutation) |
| `explicit_request` | client asks for a person or raises a complaint |

## Behavior

1. A trigger creates an `Escalation` with a **provenance bundle** — the reviewer sees the documents, the gap report, the flagged claim, and the rule source, not just the model's conclusion.
2. The case is parked: no further automatic mutation or delivery while `open`. (Reminders may still fire; they are messaging only.)
3. A human resolves with `approve` / `request_more` / `override`. `override` is itself recorded (who, what, why) and re-enters the pipeline — it does not bypass the verification gates; an override changes a *decision input*, never the fail-closed gate logic.
4. The agent, while parked, may answer questions but states uncertainty plainly and never asserts a legal conclusion it cannot source.

## The advice boundary

The agent must not present document preparation as legal advice:

- It may **state** what the requirement set says (with the source cited).
- It may **not** advise on the client's *chances*, interpret ambiguous rules, or recommend between legal options — those route to a human.
- A client asking "will I get the visa?" gets a factual status + a human referral, never a prediction.

## Stability measures

- **Provenance bundle mandatory:** an escalation without context is rejected by the queue (fail-closed).
- **Parked, not guessing:** open escalations block mutation and delivery.
- **Override is auditable and gated:** it records actor + reason and still passes the verification gates.
- **HITL gated by harness:** a module is only eligible for HITL after its harness clears the bar, so humans review residual, not noise.

## Example

```
gap-analysis finds funds £9,800 < £10,230 threshold, but a second account exists unverified
→ trigger refusal_risk → escalation created with both account docs + rule source
→ case parked, client told "checking this with a specialist"
→ human resolves request_more: "ask for the second account's verified statement"
→ pipeline resumes
```

## Test plan

1. Every trigger type produces a well-formed `Escalation` with a non-empty provenance bundle.
2. Open escalation blocks mutation and delivery (assert no writes/ships while `open`).
3. `override` is recorded with actor + reason and still passes verification gates (does not skip them).
4. Advice-boundary probe: "will I get the visa?" → factual status + referral, no prediction (assert output contains no probability/guarantee).
5. Module below harness bar → HITL path disabled for it.

## Open questions

- Human reviewer surface: minimal internal queue first (a review list + approve/request/override) vs. a dedicated UI? (Recommend minimal queue for MVP.)
- SLA for human response while a case is parked — what cadence do we promise the client? (Recommend explicit "specialist will review within X" message.)
