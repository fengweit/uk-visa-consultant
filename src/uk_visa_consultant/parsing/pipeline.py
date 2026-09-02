"""Intake entry point: attachment -> extract -> type -> fill fields -> Document.

``intake(attachment_path, mime)`` is the single call the rest of the system uses
to turn an uploaded file into a typed ``Document`` for gap-analysis.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from .extract import Extraction, extract
from .fields import extract_fields
from .profiles import get_profile
from .type import match_type
from uk_visa_consultant.llm import StubLLMClient
from uk_visa_consultant.models import Document, DocumentQuality

if TYPE_CHECKING:
    from uk_visa_consultant.llm import LLMClient

_LOW_CONFIDENCE_THRESHOLD = 0.7


def _doc_id(source_path: str) -> str:
    digest = hashlib.sha256(str(Path(source_path).resolve()).encode("utf-8")).hexdigest()[:12]
    return f"doc_{digest}"


def _build_flags(extraction: Extraction, provenance: dict, notes: list[str]) -> list[str]:
    flags: list[str] = []
    if extraction.pdf_type == "mixed":
        flags.append("mixed_layout")
    if extraction.pages_needing_ocr:
        pages = ",".join(str(i) for i in extraction.pages_needing_ocr)
        flags.append(f"needs_ocr:{pages}")
    if extraction.has_encoding_issues:
        flags.append("encoding_issues")
    if extraction.any_scanned and not extraction.full_text.strip():
        flags.append("low_quality")

    confs = [p.confidence for p in provenance.values() if p.confidence is not None]
    if confs and (sum(confs) / len(confs)) < _LOW_CONFIDENCE_THRESHOLD:
        flags.append("low_confidence")

    flags.extend(notes)
    return flags


def intake(attachment_path: str | Path, mime: str | None = None, llm: "LLMClient | None" = None,
           claimed_type: str | None = None) -> Document:
    """Convert an uploaded attachment into a structured, typed ``Document``.

    ``llm`` defaults to ``StubLLMClient`` (deterministic, pre-API-key); pass a
    real client once a provider is configured. OCR is out of scope for now.
    ``claimed_type`` is the client's stated document type (from the intent slot);
    it is used only when the PDF is image-only/scanned and has no text to match.
    """
    client: LLMClient = llm or StubLLMClient()
    path = Path(attachment_path)

    extraction = extract(path, mime)

    type_match = match_type(extraction, client)
    doc_type = type_match.type
    if doc_type == "general" and claimed_type and get_profile(claimed_type).type != "general":
        doc_type = claimed_type  # scanned doc: type from the client's claim, not text
    profile = get_profile(doc_type)

    if profile.fields:
        fields, provenance, notes = extract_fields(profile, extraction, client)
    else:
        fields, provenance, notes = {}, {}, []

    quality = DocumentQuality(
        scanned=extraction.any_scanned,
        ocr_used=extraction.ocr_used,
        extraction_confidence=extraction.classification_confidence,
    )
    flags = _build_flags(extraction, provenance, notes)

    return Document(
        id=_doc_id(str(path)),
        type=doc_type,
        source_path=str(path),
        source_pages=list(range(1, extraction.num_pages + 1)),
        fields=fields,
        provenance=provenance,
        quality=quality,
        flags=flags,
    )
