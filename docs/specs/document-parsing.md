# Spec — Document parsing

## Purpose

Convert an uploaded document (PDF, image, or text) into a **structured, typed `Document`** whose fields the gap-analysis module can check against visa requirements. This is the "reusable middle layer" for documents: a document **profile** (data) declares what to extract; the parser (code) executes it.

## Position in pipeline

```
attachment (pdf/image/text) ──► extract (text/tables/OCR) ──► type (profile match)
   ──► fill fields (schema) ──► Document ──► gap-analysis
```

## Canonical type

```jsonc
// Document
{
  "id": "doc_9c1d...",
  "type": "bank_statement",             // from the profile registry
  "source_path": "/data/uploads/c_0021/statement.pdf",
  "source_pages": [1,2,3],
  "fields": {                            // profile-defined, typed
    "account_holder": "Jane Doe",
    "bank": "HSBC UK",
    "period_start": "2026-05-01",
    "period_end": "2026-07-31",
    "closing_balance": 18420.55,
    "min_balance": 15200.00
  },
  "provenance": {                        // where each field came from
    "closing_balance": {"page": 3, "region": "table", "confidence": 0.97}
  },
  "quality": { "scanned": false, "ocr_used": false, "extraction_confidence": 0.96 },
  "flags": []                            // e.g. "name_mismatch", "period_gap", "low_quality"
}
```

## Extraction layer (per the `pdf` skill)

- **PDF with a text layer:** pypdf/pdfplumber — per-page text, tables, metadata.
- **Scanned / image-only PDF or image:** route to OCR (pymupdf fast path, marker for quality-sensitive docs); do **not** report empty text as "no content" — check for image-only pages first (`--meta` → `likely_scanned_pages` → rasterize → OCR).
- **Plain text / email body:** accepted directly.
- Output of this layer is raw per-page text + tables + a scanned/quality flag; **typing** happens in the next layer.

## Document profiles (data-driven)

A profile declares the fields and extraction hints for one document type. Adding a new document type = adding a profile file, not code.

```jsonc
{
  "type": "bank_statement",
  "match": { "keywords": ["bank statement", "statement of account", "transaction"] },
  "fields": {
    "account_holder": {"kind": "text", "hint": "account name / holder"},
    "period_start":  {"kind": "date", "hint": "statement start date"},
    "period_end":    {"kind": "date", "hint": "statement end date"},
    "closing_balance": {"kind": "money", "hint": "closing/ending balance"},
    "min_balance":   {"kind": "money", "hint": "lowest balance in period"}
  }
}
```

Extraction uses a few-shot prompt `{raw_text, profile} → fields` via `complete(prompt, schema)`; the schema is generated from the profile so a malformed/missing field is caught at validation, not at gap time.

## Document types (initial registry)

| Type | Key fields |
|---|---|
| `passport` | full_name, dob, passport_no, expiry, nationality |
| `bank_statement` | account_holder, period_start/end, closing_balance, min_balance |
| `employment_letter` | employer, employee, role, salary, start_date, signed |
| `payslip` | employee, period, gross, net |
| `invitation_letter` | inviter, invitee, relationship, address, date |
| `tb_certificate` | name, certificate_no, clinic, date, result |
| `english_test` | name, test, level/score, date, reference_no |
| `marriage_certificate` | spouse_a, spouse_b, date, place, registration_no |
| `accommodation` | address, owner/tenant, occupants, size_rooms |
| `cas` / `cos` | reference_no, sponsor, course/role, dates |
| `general` | free-text fallback (no typed fields) |

## Stability measures

- **Schema-validated fields** from the profile; a field the model can't fill is `null` with a provenance note, never guessed.
- **Confidence + flags:** low-confidence extraction → flag; gap-analysis treats flagged fields as needing verification, not as facts.
- **Provenance on every field** (page/region/confidence) so a wrong value is traceable to its source.
- **Deterministic type matching:** document type is decided by profile keyword/structural match first; LLM only disambiguates ties.

## Example I/O

```
in:  statement.pdf (3 pages, text layer, HSBC account)
type: bank_statement (keyword match)
fields: { account_holder:"Jane Doe", period_end:"2026-07-31", closing_balance:18420.55, ... }
quality: { scanned:false, extraction_confidence:0.96 }
→ passed to gap-analysis
```

## Test plan

1. Fixture PDFs per document type → assert typed fields match known ground truth.
2. Scanned (image-only) PDF → OCR path triggered, not empty text.
3. Tampered / low-quality image → `quality` + `flags` set, not silent.
4. Unknown document → `type:"general"`, no fabricated typed fields.
5. Malformed model output → schema validation fails → retry → fail-closed (fields null + provenance note).

## Open questions

- OCR quality bar: pymupdf (fast) as default with marker (quality) only for flagged docs? (Recommend yes — cost/latency.)
- Handwritten documents (rare, e.g. some declarations) — defer; flag for human review initially.
