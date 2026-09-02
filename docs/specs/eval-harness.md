# Spec — Eval harness

## Purpose

The regression-and-gate suite that makes "stable" measurable. It runs **before** human-in-the-loop is enabled, and a module is eligible for HITL only after its harness bar clears. It is the ordering constraint from `docs/STABILITY.md`: **checks before humans.**

## Scope — per-module golden sets

| Module | Golden set | Pass metric |
|---|---|---|
| intent-recognition | raw message → expected `Intent` (rule + long-tail) | exact `intent`; slot F1 |
| document-parsing | fixture PDF/image → expected typed fields | field-level accuracy |
| gap-analysis | Documents × RequirementSet → expected `GapReport` | exact `verdict` + `req_id` |
| assembly/gates | Package fixtures → expected gate verdicts | exact `verdict` (PASS/FAIL/HOLD) |
| reminder-followup | deadline fixtures → expected notifications | exact notify/no-notify |
| cover-letter | verified fields → expected claims, and **no unverified claim** | hallucination = fail |

Each fixture is a `{input, expected, meta}` triple in `evals/fixtures/<module>/`, plus a `--k` sample for model-driven long-tail cases.

## Harness contract

```
run(module) → {
  total, passed, failed,
  per_fixture: [{fixture_id, verdict, expected, actual, diff}],
  bar: 0.95,          // per-module promotion threshold (configurable)
  promoted: bool
}
```

- **Deterministic modules** (gates, scheduling, gap verdicts) must pass 100% — they are code, so a miss is a bug.
- **Model-driven modules** (rewrite, long-tail matching, field extraction, cover letter) must clear the configured bar (start 0.95) on golden sets before promotion.

## Hallucination gate (cover letter / evidence strings)

A dedicated check runs on generated prose: every material claim (a name, date, amount, or rule statement) must trace to a verified `Document` field or a `RequirementSet` entry. A claim with no provenance is a **hard fail**, independent of fluency. This is the single most important gate for this domain.

## Stability measures

- **Determinism check:** deterministic modules are run 3× and must be byte-identical — flapping is a failure.
- **Fail-closed promotion:** a module below bar is not wired into the live pipeline; the harness result is recorded with the run.
- **Versioned fixtures:** each fixture carries a version and an owner note; changing a requirement means updating its fixture in the same change (fixture and rule move together).

## Example

```
run(gap-analysis) →
  total 18, passed 18, failed 0, bar 1.00, promoted true
run(intent-recognition, --k long-tail) →
  total 30, passed 28, failed 2, bar 0.95, promoted false → fix the 2 misses
```

## Test plan (for the harness itself)

1. A deliberately broken deterministic module (mutated rule) → harness reports <100% and fails promotion.
2. A cover letter with one fabricated date → hallucination gate hard-fails.
3. Deterministic module run 3× → identical output (no flapping).
4. Fixture version bump without rule change → harness flags fixture/rule drift.

## Open questions

- Where do golden fixtures live vs. client data? Fixtures are **synthetic/redacted** only — real client material is never a fixture. (Hard rule.)
- Bar per module: single global 0.95, or per-module bars (e.g. cover-letter hallucination = 100% no-fabrication)? Recommend: hard 100% on hallucination, 0.95 on extraction accuracy.
