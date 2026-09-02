# Spec — Assembly → delivery → revision

## Purpose

The **static, deterministic** final stage: assemble a submission-ready `Package`, run the verification gates, and either deliver or return a precise revision list. Nothing leaves without passing every gate. This is the "enough checks before sending outcomes" module.

## Position in pipeline

```
Documents[] + form_data + GapReport(READY) ──► assemble ──► Package
   ──► verification gates ──► PASS → deliver
                             └─ FAIL/HOLD → revision list (never partial)
```

## Canonical type

```jsonc
// Package
{
  "package_id": "pkg_0001",
  "client_id": "c_0021",
  "visa_type": "student",
  "form_data": {           // completed application form fields (application-form answer set)
    "given_name": "Jane", "family_name": "Doe", "dob": "1998-04-02", "...": "..."
  },
  "checklist": [           // document checklist, one entry per RequirementSet doc
    {"req_id": "student.passport", "doc_id": "doc_0001", "status": "included"}
  ],
  "cover_letter": { "text": "...", "template": "cover.student.v1" },
  "supporting": ["doc_0001", "doc_0002", "..."],
  "checks": [              // every verification result — the audit trail
    {"check_id": "gate.consistency.name", "verdict": "PASS", "evidence": "name matches across passport, bank, CAS"},
    {"check_id": "gate.mandatory.all",   "verdict": "PASS", "evidence": "12/12 mandatory docs OK"}
  ]
}
```

## Assembly (static)

- Completed **form data** is assembled from extracted `Document` fields + client profile; any field not backed by a source document is marked `unverified` and blocked by a gate (a form answer must trace to evidence).
- **Checklist** and **supporting** index are generated mechanically from the `RequirementSet` and the resolved `GapReport`.
- **Cover letter** is rendered from the route's template with verified fields substituted. It is text-generation, but bounded: it may only state facts that appear in verified fields (see stability).

## Verification gates (fail-closed, run before every delivery)

| Gate | Check | Fail behavior |
|---|---|---|
| `gate.gap.ready` | `GapReport.status == READY` (no outstanding mandatory items) | block |
| `gate.mandatory.all` | every mandatory `RequirementSet` doc present + valid | block |
| `gate.consistency.*` | cross-doc equality (name, DOB, passport no, amounts) | block |
| `gate.form.complete` | no unanswered/`unverified` form field | block |
| `gate.funds.window` | funds evidence still within its validity window at submission | block |
| `gate.passport.validity` | passport valid for the required period beyond stay | block |
| `gate.provenance` | every cover-letter and form claim has a source `doc_id` | block |

Gate result is `PASS | FAIL | HOLD`. `HOLD` = cannot be verified (e.g. a flagged low-quality document) — it blocks, and routes to human review. **An unverifiable claim is `HOLD`, never `PASS`.**

## Deliver / revision loop

- **Deliver** (PASS only): emit the package to the client (via comms layer) and mark the case `DELIVERED`. Delivery itself is idempotent (dedupe by `package_id`).
- **Revision** (any FAIL/HOLD): return a revision list — exactly which `req_id`/`check_id` failed, why, and the one action each — plus the standard gap report. The loop is static: client supplies fixes → re-parse → re-run gates.

## Stability measures

- **Static assembly:** given identical inputs, assembly is byte-identical; no model in the assembly path except cover-letter rendering (which is provenance-gated).
- **Fail-closed:** any gate failure blocks delivery; there is no "override and ship anyway" path in code.
- **Full audit:** every delivered package carries its complete `checks[]`, so a shipped package can be re-verified from its own record.
- **No partial shipping:** a package either passes all gates or is not delivered — there is no "send most of it."

## Example I/O

```
assemble(Documents[12], form_data, GapReport READY) →
  Package{ checks:[
    {gate.gap.ready, PASS},
    {gate.mandatory.all, PASS, "12/12"},
    {gate.consistency.name, PASS},
    ...
  ]}
→ deliver → case DELIVERED
```

```
assemble(..., GapReport INCOMPLETE) →
  gate.gap.ready → FAIL → revision list:
    "student.cas: MISSING — provide your CAS number."
  (no delivery)
```

## Test plan

1. READY inputs → all gates PASS → delivered, case `DELIVERED`, audit present.
2. One MISSING mandatory doc → `gate.gap.ready` FAIL → no delivery; revision list names it.
3. Name mismatch across two docs → `gate.consistency.name` FAIL → block.
4. Unverified form field → `gate.form.complete` FAIL → block.
5. Low-quality flagged doc → `HOLD` → routed to human review, not delivered.
6. Identical inputs → byte-identical package (determinism).
7. Re-deliver same `package_id` → deduped (no duplicate send).

## Open questions

- Delivery format: a single combined PDF + checklist, or a structured package the client opens in a viewer? (Recommend combined PDF + human-readable checklist for MVP.)
- Digital signature / client confirmation of accuracy before submission — add a "client confirms" gate? (Recommend yes, before any real submission.)
