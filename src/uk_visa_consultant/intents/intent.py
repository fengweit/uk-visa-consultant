"""Intent recognition — rewrite → match → Intent (docs/specs/intent-recognition.md).

Two stages:
1. rewrite — deterministic normalize (lowercase, whitespace, synonym map). The
   LLM rewrite path is a hook for the long tail (not wired yet — no model set).
2. match   — rule-first keyword scoring over a versioned rule set; the LLM is
   consulted only for the long tail (hook present, returns general for now).
   Confidence is a monotone function of keyword hits.
"""
from __future__ import annotations

import re
from typing import Any

from uk_visa_consultant.models import Intent

# Ordered, versioned keyword rules — most frequent intents first. Order breaks
# ties on equal hit counts.
_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("submit_document.v1", "submit_document", (
        "here is my", "here's my", "here are my", "here're my",
        "here is the", "here's the", "here are the", "here're the",
        "my documents", "my files", "my docs",
        "sending you", "send you", "sending my", "send my",
        "attached", "attach", "upload",
        "my passport", "my bank", "bank statement", "payslip",
        "cas number", "cos number", "marriage certificate",
        "tb test", "english test", "invitation letter",
        "tenancy agreement", "employment letter",
    )),
    ("document_query.v1", "document_query", (
        "what documents", "what do i need", "which documents", "do i need",
        "required", "requirements", "checklist", "what else",
    )),
    ("gap_question.v1", "gap_question", (
        "why", "missing", "what's wrong", "what is wrong", "rejected",
        "not enough", "insufficient", "refused", "what's missing",
    )),
    ("status_check.v1", "status_check", (
        "status", "where is my", "how is my", "progress", "update", "any news",
    )),
    ("schedule.v1", "schedule", (
        "appointment", "schedule", "book", "biometrics", "reschedule", "rebook",
    )),
    ("escalate_human.v1", "escalate_human", (
        "speak to someone", "speak to a human", "human", "real person",
        "manager", "complaint", "talk to a person",
    )),
]

# keyword (rewrite-normalized) -> canonical document type, for slots
_DOC_TYPE_KEYWORDS = {
    "passport": "passport",
    "bank statement": "bank_statement",
    "payslip": "payslip",
    "cas number": "cas",
    "cos number": "cos",
    "marriage certificate": "marriage_certificate",
    "tb test": "tb_certificate",
    "tb certificate": "tb_certificate",
    "english test": "english_test",
    "invitation letter": "invitation_letter",
    "tenancy agreement": "accommodation",
    "employment letter": "employment_letter",
}

# a requirements question outranks a bare document-type mention
_QUESTION_MARKERS = ("?", "do i need", "what", "which", "should i",
                     "is it required", "do i have to", "can i")

_SYNONYMS = {"docs": "documents", "doc": "document", "u": "you", "ur": "your",
             "pls": "please", "plz": "please", "thx": "thanks"}


def rewrite(text: str) -> str:
    """Deterministic rewrite: lowercase, collapse whitespace, expand synonyms."""
    t = re.sub(r"\s+", " ", text.lower().strip())
    for k, v in _SYNONYMS.items():
        t = re.sub(rf"\b{k}\b", v, t)
    return t


def _match(canonical: str) -> tuple[str, str, int] | None:
    best: tuple[str, str, int] | None = None
    for rule_id, intent, keywords in _RULES:
        hits = sum(1 for kw in keywords if kw in canonical)
        if intent == "document_query" and hits > 0 and any(m in canonical for m in _QUESTION_MARKERS):
            hits += 2  # question boost: "do I need X?" is a query, not a submission
        if hits and (best is None or hits > best[2]):
            best = (intent, rule_id, hits)
    return best


def _confidence(hits: int) -> float:
    return round(min(0.95, 0.55 + 0.15 * hits), 2)


def _slots(intent: str, canonical: str) -> dict[str, Any]:
    if intent != "submit_document":
        return {}
    for kw, dtype in _DOC_TYPE_KEYWORDS.items():
        if kw in canonical:
            return {"document_type": dtype}
    return {}


class IntentRecognizer:
    def __init__(self, llm: Any | None = None):
        self.llm = llm  # reserved for long-tail LLM rewrite/match (not yet wired)

    def recognize(self, text: str) -> Intent:
        canonical = rewrite(text)
        match = _match(canonical)
        if match is not None:
            intent, rule_id, hits = match
            return Intent(
                intent=intent,
                confidence=_confidence(hits),
                slots=_slots(intent, canonical),
                rewrite_of=text,
                matched_rule=rule_id,
                needs_clarification=False,
            )
        # Long tail: no rule fired. LLM hook lives here (returns general until a
        # model is configured); fail closed to clarification.
        return Intent(intent="general", confidence=0.5, rewrite_of=text,
                      matched_rule=None, needs_clarification=True)
