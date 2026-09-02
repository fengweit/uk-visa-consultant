# Delivery stability

This repository's second deliverable: a concrete answer to *"how do you make AI delivery stable, and how does that drive agent selection and workflow design?"*

The failure mode this project must not have: a confident, fluent agent that assembles an application package with a wrong field, a missing document, or a fabricated rule — and ships it. Stability is designed in as **constraints on every agent boundary**, not bolted on as review.

## The five levers

### 1. Structured output everywhere

No agent returns free text that another module must parse by convention. Every agent boundary declares a schema; every LLM response is parsed and **validated** against it. A response that fails schema is retried once, then the boundary fails closed.

- `complete(prompt, schema) -> ValidatedResult` — the only way a model is called.
- `ValidatedResult` carries `raw`, `parsed`, `schema_errors`, and the model/params used.

**Agent-selection consequence:** an agent is chosen for a role only if its output is a schema-fittable record. Free-form "advice" agents are restricted to the conversation surface, never to pipeline internals.

### 2. Data, not model judgment, is the source of truth

Requirements, thresholds, and validity windows live in the visa module (`RequirementSet`) as **data with provenance** — each rule cites its source (gov.uk page + accessed date). The model is used to *extract and compare*, never to *invent a rule*.

- Gap verdicts are computed by comparing extracted `Document` fields against `RequirementSet` rules.
- The model can fill "why this is insufficient, in plain language," but the `verdict` field itself is a deterministic check result.

### 3. Fail-closed gates before delivery

`assembly → verification gates → deliver`. Gates are deterministic, enumerable, and **fail closed**: `PASS` ships, `FAIL`/`HOLD` blocks, and an unverifiable check is `HOLD`, not `PASS`.

- No partial shipping: a package with one `MISSING` mandatory document never reaches the client.
- Gate results are stored on the `Package` as `VerificationResult[]` with evidence + provenance, so every shipped package is auditable.

### 4. Idempotent, exact-intent recovery

- **Recovery is exact-intent and GET-only.** Retrying a failed step re-runs the same deterministic operation; it never invents a compensating mutation.
- **Ambiguous mutations hold.** If the system cannot determine intent unambiguously (e.g. "change my address" when two addresses appear), it emits a clarifying question and parks the case — it does not guess and write.
- Every mutation (form-data write, document association) is idempotent by key and logged.

### 5. Confidence-gated escalation

Every model-derived value carries a confidence. Below threshold — or on any refusal-risk pattern — the case routes to a human with provenance attached, and the agent states its uncertainty rather than covering it. See `docs/specs/human-in-the-loop.md`.

## Ordering: harness before humans

The eval harness (`docs/specs/eval-harness.md`) is built **before** human-in-the-loop is switched on. A module is eligible for HITL only after its golden-set pass rate clears a bar. Humans review the *residual* — the cases the deterministic gates and high-confidence model paths already couldn't resolve — not the whole volume.

## Workflow design principles (what this implies)

1. **Thin channels, fat core** — transport is isolated and tested alone; the core loop is network-free.
2. **One typed record per boundary** — no shared mutable state between modules; modules are functions of records.
3. **Deterministic where possible, model where necessary** — scheduling, gap verdicts, assembly, and gates are code; only rewrite/extraction/comparison/reasoning are model calls.
4. **Provenance on every material claim** — a shipped package can be traced back to a source document and a rule.
5. **Observability by default** — every step logs `{module, input_hash, output_hash, verdict, confidence, model?}` so a failure is attributable to a step, not a vibe.

## What "stable" means here, measurably

- Harness pass rates per module (intent, parsing, gap) above a set bar on golden sets.
- Zero shipped packages with an unresolved mandatory gap.
- Deterministic gates reproduce identical verdicts on identical inputs (no flapping).
- Every shipped package carries a complete `VerificationResult[]` audit.
