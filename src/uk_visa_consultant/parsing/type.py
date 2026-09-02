"""Deterministic document-type matching.

Keyword + structural (regex) scoring runs first; the LLM is consulted *only* to
disambiguate a tie among equally-scoring profiles (and even then only when an
LLM client is supplied — otherwise the registry order breaks the tie and the
confidence is marked low).

Per docs/specs/document-parsing.md: "document type is decided by profile
keyword/structural match first; LLM only disambiguates ties."
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .extract import Extraction
from .profiles import DocumentProfile, all_profiles, get_profile

if TYPE_CHECKING:
    from uk_visa_consultant.llm import LLMClient


class TypeMatch(BaseModel):
    type: str
    confidence: float
    matched_by: str = "fallback"  # keywords | structural | llm | fallback
    candidates: list[str] = []


class _TypeChoice(BaseModel):
    type: str


def _score(profile: DocumentProfile, text_lower: str) -> tuple[int, int]:
    """Return (keyword_hits, pattern_hits) for a profile against lowered text."""
    kw = sum(1 for k in profile.match.keywords if k.lower() in text_lower)
    pat = 0
    for pattern in profile.match.patterns:
        try:
            pat += len(re.findall(pattern, text_lower, flags=re.IGNORECASE))
        except re.error:  # pragma: no cover - defensive
            continue
    return kw, pat


def _confidence(total_score: int) -> float:
    """Monotone, capped confidence from a deterministic match score."""
    return round(min(0.95, 0.6 + 0.1 * total_score), 2)


def match_type(extraction: Extraction, llm: "LLMClient | None" = None) -> TypeMatch:
    """Classify an extraction into a document type from the profile registry."""
    text_lower = extraction.full_text.lower()

    ranked: list[tuple[DocumentProfile, int, str]] = []
    for profile in all_profiles():
        kw, pat = _score(profile, text_lower)
        total = kw + 2 * pat  # structural signals weighted above keywords
        if total <= 0:
            continue
        matched_by = "structural" if (pat > 0 and kw == 0) else "keywords"
        ranked.append((profile, total, matched_by))

    if not ranked:
        return TypeMatch(type="general", confidence=1.0, matched_by="fallback", candidates=[])

    ranked.sort(key=lambda r: -r[1])
    top_score = ranked[0][1]
    tied = [r for r in ranked if r[1] == top_score]
    candidates = [r[0].type for r in ranked]

    if len(tied) == 1:
        profile, score, matched_by = tied[0]
        return TypeMatch(
            type=profile.type,
            confidence=_confidence(score),
            matched_by=matched_by,
            candidates=candidates,
        )

    return _disambiguate([r[0].type for r in tied], extraction, llm, candidates)


def _disambiguate(
    tied: list[str],
    extraction: Extraction,
    llm: "LLMClient | None",
    candidates: list[str],
) -> TypeMatch:
    if llm is None:
        # No LLM to break the tie: registry order is the deterministic fallback.
        return TypeMatch(
            type=tied[0],
            confidence=0.5,
            matched_by="fallback",
            candidates=candidates,
        )

    prompt = (
        "A document matches more than one type equally. Choose the single most "
        "likely type.\n\nCandidate types: "
        + ", ".join(tied)
        + "\n\nDocument text:\n"
        + (extraction.full_text or "(no text layer)")
        + '\n\nReturn JSON: {"type": "<chosen type>"}'
    )
    result = llm.complete(prompt, schema=_TypeChoice)
    if result.parsed is not None and result.parsed.type in tied:
        return TypeMatch(
            type=result.parsed.type,
            confidence=0.6,
            matched_by="llm",
            candidates=candidates,
        )
    # LLM failed closed -> registry order.
    return TypeMatch(type=tied[0], confidence=0.5, matched_by="fallback", candidates=candidates)


def is_typed(doc_type: str) -> bool:
    """True unless the document fell back to the free-text ``general`` type."""
    return get_profile(doc_type).type != "general"
