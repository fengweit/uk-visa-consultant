# Spec — Intent recognition (rewrite + matching)

## Purpose

Turn a raw client message into a typed `Intent` the router can act on. Two stages, deliberately separated so each is testable in isolation:

1. **Rewrite** — normalize noise (typos, slang, code-switching, run-on phrasing) into a canonical statement.
2. **Match** — classify the canonical statement against a fixed intent taxonomy and extract slots.

## Position in pipeline

```
Message ──► rewrite ──► canonical_statement ──► match ──► Intent ──► router
```

## Canonical type

```jsonc
// Intent
{
  "intent": "submit_document",           // one of the taxonomy below
  "confidence": 0.93,                    // 0..1 from the matcher
  "slots": {                             // intent-specific extracted values
    "document_type": "bank_statement"
  },
  "rewrite_of": "i hav my bank statemnt here u go",
  "matched_rule": "submit_document.v1",  // which rule fired (provenance)
  "needs_clarification": false
}
```

## Intent taxonomy

| Intent | Meaning | Key slots |
|---|---|---|
| `submit_document` | client sends / promises a document | `document_type`, `attachment_ref?` |
| `document_query` | asks what documents are needed | `visa_type?` |
| `gap_question` | asks why something is missing/wrong | `document_type?` |
| `status_check` | asks where the application stands | — |
| `schedule` | wants to set/change a follow-up or appointment | `when?`, `what?` |
| `general` | everything else, answered conversationally | — |
| `escalate_human` | explicitly asks for a person / expresses complaint | — |

## Stage 1 — Rewrite

- **Input:** raw `Message.body` (single turn).
- **Output:** `canonical_statement` — one clear sentence, de-noised, entity-normalized (dates → ISO, doc-type names → taxonomy terms).
- **Implementation:** few-shot LLM via `complete(prompt, schema)`; a deterministic fallback (lowercase, whitespace collapse, a small synonym map) is used when the LLM is unavailable so the loop still runs.
- **Rule:** rewrite must preserve meaning; if it cannot, it returns the input unchanged and flags `needs_clarification` downstream.

## Stage 2 — Match

- **Input:** `canonical_statement`.
- **Rule-first:** an ordered list of keyword/pattern rules (each with a versioned id, e.g. `submit_document.v1`) is evaluated first. A rule hit returns immediately with high confidence.
- **LLM fallback:** no rule hit → a classification prompt returns `{intent, confidence, slots}`; the long tail is covered by the model, the common cases stay deterministic and cheap.
- **Confidence threshold:** below `0.6` → `needs_clarification=true`; the router then asks the client one disambiguating question rather than guessing.

## Router contract (consumer)

The router maps `Intent.intent` to a specialist:

```
submit_document → document-parsing (attachment) then gap-analysis
document_query  → requirement lookup (visa module)
gap_question    → gap-analysis explainer
status_check    → case status snapshot
schedule        → reminder-followup
escalate_human  → human-in-the-loop
general         → conversational surface (bounded, no pipeline writes)
```

## Stability measures

- **Schema-validated** `Intent` on every match; malformed model output retries once then fails closed to `needs_clarification`.
- **Deterministic rules first** — the top-N frequent intents never depend on model nondeterminism.
- **`matched_rule` provenance** — every intent records how it was decided (rule id or `model`), so a wrong route is attributable.
- **No mutation here** — intent recognition only classifies; it never writes to the case.

## Example I/O

```
in:  "i hav my bank statemnt here u go"  (attachment: statement.pdf)
rewrite: "I am submitting my bank statement"
match: {intent:"submit_document", slots:{document_type:"bank_statement"},
        confidence:0.95, matched_rule:"submit_document.v1"}

in:  "do I really need a TB test??"
rewrite: "Do I need a TB test?"
match: {intent:"document_query", slots:{}, confidence:0.7, matched_rule:"document_query.v1"}
→ router may surface a clarification if the visa type is ambiguous (TB depends on country of residence).
```

## Test plan

1. Golden set of ~50 raw→intent pairs per frequent intent; rule path must be deterministic (byte-identical on repeat).
2. Rewrite unit tests: typos/slang normalized; dates → ISO; meaning preserved on ambiguous input.
3. Low-confidence inputs route to `needs_clarification`.
4. Malformed model output → retried, then fail-closed to clarification (no crash, no guess).
5. `matched_rule` provenance present on every result.

## Open questions

- Synonym map size: keep small and curated vs. auto-grow? (Recommend curated, versioned.)
- Do we need intent *sequences* (multi-turn slots, e.g. "submit_document" split across two messages)? Defer until a real case needs it.
