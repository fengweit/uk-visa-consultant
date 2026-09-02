# Spec — Gap analysis

## Purpose

Compare parsed `Document`s against the visa route's `RequirementSet` and produce a **standardized `GapReport`** telling the client exactly what is missing, wrong, expiring, or inconsistent — and the single action that fixes it. This is the module that turns "I sent you some documents" into "here is precisely what still stands between you and submission."

## Position in pipeline

```
Documents[] × RequirementSet ──► check every requirement ──► GapReport
```

## Canonical type — the standard pattern/format

Every gap report, regardless of visa route or client, uses this one format:

```jsonc
// GapReport
{
  "client_id": "c_0021",
  "visa_type": "student",
  "generated_at": "2026-09-01T14:30:00Z",
  "status": "INCOMPLETE | READY | BLOCKED",     // READY = every mandatory check OK
  "items": [
    {
      "req_id": "student.funds.28day",          // id in the RequirementSet (provenance)
      "req_name": "Maintenance funds — 28-day hold",
      "doc_id": "doc_9c1d",                     // null when no document supplied
      "verdict": "OK | MISSING | INVALID | EXPIRING | INCONSISTENT",
      "evidence": "closing_balance 18420.55 ≥ required 10230.00; period 2026-05-01..07-31 covers 28 days",
      "action": null | "Provide a bank statement showing ≥ £10,230 held for 28 consecutive days ending within the last 31 days.",
      "severity": "mandatory | recommended"
    }
  ]
}
```

### Verdicts (deterministic, computed — not model-generated)

| Verdict | Meaning |
|---|---|
| `OK` | requirement satisfied, evidence present |
| `MISSING` | required document not supplied |
| `INVALID` | supplied but wrong (wrong type, expired, below threshold, malformed) |
| `EXPIRING` | valid now but fails within the application window (e.g. passport expires during stay) |
| `INCONSISTENT` | conflicts with another document (name/DOB/amount mismatch) |

## The three checks per requirement

For every entry in the `RequirementSet`, run in order:

1. **Presence** — is a document of the required type attached?
2. **Value** — does its extracted field satisfy the rule (threshold, date window, format)?
3. **Applicability** — does the rule apply to *this* client (e.g. maintenance-funds exemption when a sponsor certifies it; TB test only for listed countries)?

Applicability is resolved from client profile facts, so the same `RequirementSet` serves different clients without per-client rule edits.

## Where the model is and is not used

- **Code (deterministic):** the verdict itself — threshold comparison, date-window math, presence check, cross-doc field equality. This must be reproducible, byte-identical on the same inputs.
- **Model (few-shot):** turning the raw comparison into the human-readable `evidence` string and the `action` sentence; flagging `INCONSISTENT` cases where the mismatch is semantic (name variant "J. Doe" vs "Jane Doe") rather than literal.
- **Rules are data:** every threshold, window, and exemption lives in the visa module with a source citation. The model never supplies a rule.

## Few-shot examples

The model path is driven by few-shot examples of `{requirement, extracted fields, → verdict narrative}`. A starter set lives in `evals/fixtures/gap/` and doubles as the harness golden set. Examples must cover each verdict type and the tricky `INCONSISTENT` variants (name variants, currency/format differences).

## Stability measures

- **Deterministic verdicts:** same inputs → same `verdict` every time (no model nondeterminism in the decision).
- **Provenance:** `req_id` links every item back to the `RequirementSet` entry and its gov.uk source.
- **Fail-closed:** a requirement whose document field failed to extract is `INVALID`/flagged for verification, never silently `OK`.
- **No invented requirements:** the report can only reference `req_id`s present in the `RequirementSet`.

## Example I/O

```
in:  Documents[passport(exp 2027-03), bank_statement(closing 18420.55, period ends 2026-07-31)]
     × RequirementSet[student]
out: status INCOMPLETE
     - student.cas            MISSING   → action: "Provide your CAS number."
     - student.funds.28day    OK        → evidence: "£18,420.55 ≥ £10,230.00, period covers 28 days"
     - student.passport       OK
     - student.tb             (applicability: country not listed) → skipped, marked "not applicable"
```

## Test plan

1. Golden fixtures: for each verdict type, assert the exact `verdict` + `req_id`.
2. Determinism: run the same fixture 3× → identical `items` (verdict + evidence hash stable).
3. Applicability: sponsor-certified-maintenance client → funds rule skipped with "not applicable".
4. Semantic mismatch ("J. Doe" vs "Jane Doe") → `INCONSISTENT` (flagged for review) rather than a hard fail.
5. Extracted-field-missing → `INVALID`, never `OK`.
6. Report references only `req_id`s present in the `RequirementSet` (no hallucinated requirements).

## Open questions

- Currency handling: convert foreign-currency balances to GBP for threshold checks? (Recommend: flag + manual review for non-GBP, don't auto-convert.)
- `INCONSISTENT` auto-resolution: semantic name variants may be auto-merged with human approval; keep gated behind HITL initially.
