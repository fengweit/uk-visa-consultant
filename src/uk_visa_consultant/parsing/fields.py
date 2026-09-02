"""Field extraction: profile fields -> pydantic schema -> LLM -> typed values.

Per docs/specs/document-parsing.md: extraction uses a few-shot prompt
``{raw_text, profile} -> fields`` via ``LLMClient.complete(prompt, schema)``.
The schema is generated from the profile so a malformed/missing field is caught
at validation time, not later. A field the model cannot fill is ``null`` with a
provenance note — never guessed.

Provenance (page/region/confidence) is computed deterministically by locating
each extracted value in the source text; values the model produced but that do
not appear verbatim are kept (they may be normalized dates/money) but marked
``region="llm"`` with a lower confidence so gap-analysis treats them as needing
verification.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, create_model

from .extract import Extraction
from .profiles import DocumentProfile, FieldSpec
from uk_visa_consultant.models import FieldProvenance

if TYPE_CHECKING:
    from uk_visa_consultant.llm import LLMClient

_KIND_TO_TYPE: dict[str, type] = {
    "text": str,
    "date": str,
    "money": float,
    "int": int,
    "float": float,
    "bool": bool,
}

# Provenance confidences
_CONF_VERBATIM = 0.97
_CONF_LLM = 0.5
_CONF_TABLE = 0.95


def build_schema(profile: DocumentProfile) -> type[BaseModel]:
    """Generate a pydantic model whose fields mirror the profile (all Optional)."""
    definitions: dict[str, Any] = {}
    for name, spec in profile.fields.items():
        base = _KIND_TO_TYPE.get(spec.kind, str)
        definitions[name] = (Optional[base], None)
    return create_model(f"{profile.type.title()}Fields", **definitions)


def build_prompt(profile: DocumentProfile, extraction: Extraction) -> str:
    """Few-shot-style extraction prompt from the profile + raw document text."""
    lines = [
        "You are extracting structured fields from a UK visa application document.",
        f"Document type: {profile.type}",
        "",
        "Document text:",
        extraction.full_text or "(no text layer — image-only document)",
        "",
        "Return a JSON object matching the requested schema exactly.",
        "If a field cannot be determined from the document, set it to null. Never guess or fabricate a value.",
        "",
        "Fields to extract:",
    ]
    for name, spec in profile.fields.items():
        lines.append(f"- {name} ({spec.kind}): {spec.hint}")
    lines += [
        "",
        "Rules:",
        "- Dates as YYYY-MM-DD where possible.",
        "- Money as a bare number (no currency symbol or thousands separators).",
        "- Booleans as true/false.",
        "- Preserve names, numbers and references exactly as printed.",
    ]
    return "\n".join(lines)


def _variants(value: Any) -> list[str]:
    """String forms of a value to search for in the source text (longest first)."""
    variants = {str(value)}
    if isinstance(value, float):
        variants.add(f"{value:,.2f}")
        variants.add(f"{value:.2f}")
        if value == int(value):
            variants.add(str(int(value)))
    elif isinstance(value, int):
        variants.add(f"{value:,}")
    return sorted(variants, key=len, reverse=True)


def _locate(value: Any, extraction: Extraction) -> FieldProvenance:
    """Find where a field value came from: (page, region, confidence)."""
    variants = _variants(value)
    for page in extraction.pages:
        # tables first (higher confidence, structured)
        for line in extraction.table_lines(page.page):
            if any(v in line for v in variants):
                return FieldProvenance(page=page.page, region="table", confidence=_CONF_TABLE)
        if any(v in page.text for v in variants):
            return FieldProvenance(page=page.page, region="text", confidence=_CONF_VERBATIM)
    # model produced a value we cannot trace verbatim (normalization)
    return FieldProvenance(region="llm", confidence=_CONF_LLM)


def extract_fields(
    profile: DocumentProfile,
    extraction: Extraction,
    llm: "LLMClient",
) -> tuple[dict[str, Any], dict[str, FieldProvenance], list[str]]:
    """Fill a profile's fields via the LLM; returns (fields, provenance, notes).

    Fail-closed: on a schema-validation failure the boundary returns all-null
    fields (with an ``unfilled`` provenance note) rather than guessed values.
    """
    schema = build_schema(profile)
    result = llm.complete(build_prompt(profile, extraction), schema=schema)

    notes: list[str] = []
    if result.parsed is not None:
        values: dict[str, Any] = result.parsed.model_dump()
    else:
        values = {name: None for name in profile.fields}
        notes.append("schema_validation_failed")

    provenance: dict[str, FieldProvenance] = {}
    for name in profile.fields:
        value = values.get(name)
        if value is None:
            provenance[name] = FieldProvenance(region="unfilled", confidence=None)
        else:
            provenance[name] = _locate(value, extraction)

    return values, provenance, notes
