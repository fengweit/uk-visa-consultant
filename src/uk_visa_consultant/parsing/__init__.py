"""Document-parsing intake path: attachment -> extract -> type -> Document."""

from .extract import Extraction, PageContent, extract, extract_image_file, extract_pdf, extract_text_file
from .fields import build_prompt, build_schema, extract_fields
from .pipeline import intake
from .profiles import (
    DocumentProfile,
    FieldSpec,
    MatchSpec,
    all_profiles,
    get_profile,
)
from .type import TypeMatch, is_typed, match_type

__all__ = [
    "DocumentProfile",
    "Extraction",
    "FieldSpec",
    "MatchSpec",
    "PageContent",
    "TypeMatch",
    "all_profiles",
    "build_prompt",
    "build_schema",
    "extract",
    "extract_fields",
    "extract_image_file",
    "extract_pdf",
    "extract_text_file",
    "get_profile",
    "intake",
    "is_typed",
    "match_type",
]
