"""Canonical data model — the shared contract between modules.

These types mirror the data model in docs/ARCHITECTURE.md. Every module boundary
exchanges these records; nothing hand-rolls its own representation. Keep this
file dependency-light (pydantic only) and do not add module-specific fields here
— extend the module that needs them instead.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    LOCAL = "local"


class Attachment(BaseModel):
    kind: str  # "pdf" | "image" | "text"
    local_path: str
    mime: str


class Message(BaseModel):
    id: str
    client_id: str
    channel: Channel
    ts: datetime = Field(default_factory=_utcnow)
    body: str = ""
    attachments: list[Attachment] = Field(default_factory=list)
    thread_id: str | None = None  # this email's own Message-ID (In-Reply-To target)
    thread_root: str | None = None  # conversation root Message-ID (the case identity)
    references: list[str] = Field(default_factory=list)  # full References chain


class SendReceipt(BaseModel):
    ok: bool
    external_id: str | None = None
    error: str | None = None


class Contact(BaseModel):
    phone: str | None = None
    email: str | None = None


class Client(BaseModel):
    id: str
    contact: Contact = Field(default_factory=Contact)
    visa_type: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict)


class Intent(BaseModel):
    intent: str
    confidence: float
    slots: dict[str, Any] = Field(default_factory=dict)
    rewrite_of: str | None = None
    matched_rule: str | None = None
    needs_clarification: bool = False


class FieldProvenance(BaseModel):
    page: int | None = None
    region: str | None = None
    confidence: float | None = None


class DocumentQuality(BaseModel):
    scanned: bool = False
    ocr_used: bool = False
    extraction_confidence: float | None = None


class Document(BaseModel):
    id: str
    type: str
    source_path: str
    source_pages: list[int] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    quality: DocumentQuality = Field(default_factory=DocumentQuality)
    flags: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    req_id: str
    name: str
    mandatory: bool = False
    rules: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None  # gov.uk URL


class RequirementSet(BaseModel):
    visa_type: str
    route: str
    requirements: list[Requirement] = Field(default_factory=list)


class GapItem(BaseModel):
    req_id: str
    req_name: str
    doc_id: str | None = None
    verdict: str  # OK | MISSING | INVALID | EXPIRING | INCONSISTENT
    evidence: str | None = None
    action: str | None = None
    severity: str = "mandatory"


class GapReport(BaseModel):
    client_id: str
    visa_type: str
    generated_at: datetime = Field(default_factory=_utcnow)
    status: str = "INCOMPLETE"  # INCOMPLETE | READY | BLOCKED
    items: list[GapItem] = Field(default_factory=list)


class VerificationResult(BaseModel):
    check_id: str
    verdict: str  # PASS | FAIL | HOLD
    evidence: str | None = None
    provenance: str | None = None


class Package(BaseModel):
    package_id: str
    client_id: str
    visa_type: str
    form_data: dict[str, Any] = Field(default_factory=dict)
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    cover_letter: dict[str, Any] = Field(default_factory=dict)
    supporting: list[str] = Field(default_factory=list)
    checks: list[VerificationResult] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    client_id: str
    state: str = "intake"  # intake | gathering | review | delivered | parked
    documents: list[Document] = Field(default_factory=list)
    gaps: GapReport | None = None
    package: Package | None = None
    deadlines: list[dict[str, Any]] = Field(default_factory=list)
