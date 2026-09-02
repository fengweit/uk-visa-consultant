# uk-visa-consultant

A human-like UK visa application consultant agent. It interacts with clients over WhatsApp and email the way a human consultant would — intake, document gathering, gap analysis, reminders, and final assembly of a submission-ready application package — and **delivers the result**, not just advice.

Built **delivery-stability-first**: every agent boundary uses structured output, every deliverable passes a fail-closed verification gate before it ships, and every claim carries provenance. The core is channel-agnostic and fully testable over a **local message loop** (no network) before any WhatsApp/email integration exists.

## What this repository contains

Two intertwined deliverables:

1. **The product** — a consultant agent that takes a client from *"I want a UK visa"* to a complete, checked application package (form data, document checklist, cover letter, indexed supporting documents).
2. **The thesis** — how to make AI delivery stable: agent selection, workflow design, structured outputs, evaluation gates, exact-intent recovery, and human escalation. Written up in [`docs/STABILITY.md`](docs/STABILITY.md).

## Visa routes (each its own module)

| Module | Route | Status |
|---|---|---|
| `visas/visitor` | Standard Visitor | spec |
| `visas/student` | Student Route | spec |
| `visas/worker` | Skilled Worker | spec |
| `visas/spouse` | Spouse / Partner (Family Route) | spec |

Each visa module is a self-contained `RequirementSet`: required documents, financial rules, refusal-risk factors, a cover-letter template, and the assembled-deliverable checklist. See [`docs/visas/`](docs/visas/).

## Pipeline

```
channel (WhatsApp / Email / Local)
  → comms layer            (normalize to canonical Message)
  → intent recognition     (rewrite → match → Intent)
  → router                 (dispatch to specialist)
  → document parsing       (pdf/image → structured Document)
  → gap analysis           (Documents × RequirementSet → GapReport)
  → assembly               (checked Package)
  → verification gates     (fail-closed, before delivery)
  → deliver / revision
  → reminder + follow-up   (deadline scheduler)
  → human-in-the-loop      (gated by the eval harness)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full data model and module contracts.

## Repository layout

```
uk-visa-consultant/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md        # data model, module contracts, pipeline
│   ├── STABILITY.md           # the delivery-stability thesis
│   ├── specs/                 # one detailed spec per core module
│   │   ├── comms-layer.md
│   │   ├── intent-recognition.md
│   │   ├── document-parsing.md
│   │   ├── gap-analysis.md
│   │   ├── reminder-followup.md
│   │   ├── assembly-delivery-revision.md
│   │   ├── eval-harness.md
│   │   └── human-in-the-loop.md
│   └── visas/                 # one module per visa route
│       ├── visitor.md
│       ├── student.md
│       ├── worker.md
│       └── spouse.md
└── (code lands here as modules are implemented: channels/, pipeline/, agents/, evals/)
```

## Status

Specification phase. The architecture and per-module specs are written; code implementation follows spec-by-spec. The first runnable loop is intended to be **local-message → intent → parse → gap → assemble → verify**, with the DeepSeek API wired in only after the loop is testable.

## Compliance note

UK immigration **advice** is regulated by the OISC. This project is positioned as **document preparation and assembly** — collecting, parsing, checking, and packaging materials against published requirements — not as legal advice. Production use requires a clear advice boundary, client disclaimers, and (where applicable) OISC registration. Requirement values in the visa specs are illustrative and must be sourced from current gov.uk guidance before production.
