"""Data-driven document-profile registry.

A profile declares the fields + extraction hints for one document type. Adding a
new document type = adding a profile here, not writing parser code. ``type.py``
uses ``match`` (keywords + structural regex patterns) for deterministic typing;
``fields.py`` turns ``fields`` into a pydantic schema for LLM extraction.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

KIND_TEXT = "text"
KIND_DATE = "date"
KIND_MONEY = "money"
KIND_INT = "int"
KIND_BOOL = "bool"


class FieldSpec(BaseModel):
    kind: str = KIND_TEXT  # text | date | money | int | bool
    hint: str = ""


class MatchSpec(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)  # structural regex hints


class DocumentProfile(BaseModel):
    type: str
    match: MatchSpec = Field(default_factory=MatchSpec)
    fields: dict[str, FieldSpec] = Field(default_factory=dict)


def _f(kind: str, hint: str) -> FieldSpec:
    return FieldSpec(kind=kind, hint=hint)


# --- Registry (ordered: more specific types first) --------------------------

PASSPORT = DocumentProfile(
    type="passport",
    match=MatchSpec(
        keywords=[
            "passport",
            "passport number",
            "place of birth",
            "date of birth",
            "nationality",
            "issuing authority",
            "machine readable zone",
        ],
        patterns=[r"[A-Z0-9<]*<[A-Z0-9<]{20,}"],  # MRZ line (contains '<')
    ),
    fields={
        "full_name": _f(KIND_TEXT, "full name / surname and given names"),
        "dob": _f(KIND_DATE, "date of birth"),
        "passport_no": _f(KIND_TEXT, "passport document number"),
        "expiry": _f(KIND_DATE, "date of expiry / expiration"),
        "nationality": _f(KIND_TEXT, "nationality / issuing country"),
    },
)

BANK_STATEMENT = DocumentProfile(
    type="bank_statement",
    match=MatchSpec(
        keywords=[
            "bank statement",
            "statement of account",
            "account number",
            "sort code",
            "transaction",
            "closing balance",
            "opening balance",
            "available balance",
        ],
        patterns=[r"(?i)(closing|opening|ending|available)\s+balance"],
    ),
    fields={
        "account_holder": _f(KIND_TEXT, "account name / holder"),
        "period_start": _f(KIND_DATE, "statement period start date"),
        "period_end": _f(KIND_DATE, "statement period end date"),
        "closing_balance": _f(KIND_MONEY, "closing/ending balance"),
        "min_balance": _f(KIND_MONEY, "lowest/minimum balance in the period"),
    },
)

EMPLOYMENT_LETTER = DocumentProfile(
    type="employment_letter",
    match=MatchSpec(
        keywords=[
            "employment",
            "letter of employment",
            "offer of employment",
            "employer",
            "annual salary",
            "job title",
            "start date",
        ],
    ),
    fields={
        "employer": _f(KIND_TEXT, "employer / company name"),
        "employee": _f(KIND_TEXT, "employee full name"),
        "role": _f(KIND_TEXT, "job title / role"),
        "salary": _f(KIND_MONEY, "annual salary"),
        "start_date": _f(KIND_DATE, "employment start date"),
        "signed": _f(KIND_BOOL, "is the letter signed?"),
    },
)

PAYSLIP = DocumentProfile(
    type="payslip",
    match=MatchSpec(
        keywords=["payslip", "pay slip", "gross pay", "net pay", "wage", "salary slip"],
    ),
    fields={
        "employee": _f(KIND_TEXT, "employee name"),
        "period": _f(KIND_TEXT, "pay period"),
        "gross": _f(KIND_MONEY, "gross pay"),
        "net": _f(KIND_MONEY, "net pay"),
    },
)

INVITATION_LETTER = DocumentProfile(
    type="invitation_letter",
    match=MatchSpec(
        keywords=["invitation letter", "invitation", "inviting", "invitee", "host"],
    ),
    fields={
        "inviter": _f(KIND_TEXT, "inviter / host name"),
        "invitee": _f(KIND_TEXT, "invitee name"),
        "relationship": _f(KIND_TEXT, "relationship between inviter and invitee"),
        "address": _f(KIND_TEXT, "address where the invitee will stay"),
        "date": _f(KIND_DATE, "letter date"),
    },
)

TB_CERTIFICATE = DocumentProfile(
    type="tb_certificate",
    match=MatchSpec(
        keywords=["tuberculosis", "tb certificate", "tb test", "tb screening", "sputum"],
    ),
    fields={
        "name": _f(KIND_TEXT, "applicant name"),
        "certificate_no": _f(KIND_TEXT, "certificate number"),
        "clinic": _f(KIND_TEXT, "clinic / test centre"),
        "date": _f(KIND_DATE, "test / certificate date"),
        "result": _f(KIND_TEXT, "result (e.g. clear)"),
    },
)

ENGLISH_TEST = DocumentProfile(
    type="english_test",
    match=MatchSpec(
        keywords=["ielts", "toefl", "english language test", "english test", "cefr", "pte academic", "selt"],
    ),
    fields={
        "name": _f(KIND_TEXT, "candidate name"),
        "test": _f(KIND_TEXT, "test name (e.g. IELTS)"),
        "level": _f(KIND_TEXT, "CEFR level / band score"),
        "date": _f(KIND_DATE, "test date"),
        "reference_no": _f(KIND_TEXT, "reference / test report number"),
    },
)

MARRIAGE_CERTIFICATE = DocumentProfile(
    type="marriage_certificate",
    match=MatchSpec(
        keywords=["marriage certificate", "certificate of marriage", "marriage", "solemnized"],
    ),
    fields={
        "spouse_a": _f(KIND_TEXT, "first spouse full name"),
        "spouse_b": _f(KIND_TEXT, "second spouse full name"),
        "date": _f(KIND_DATE, "date of marriage"),
        "place": _f(KIND_TEXT, "place of marriage"),
        "registration_no": _f(KIND_TEXT, "registration number"),
    },
)

ACCOMMODATION = DocumentProfile(
    type="accommodation",
    match=MatchSpec(
        keywords=["accommodation", "tenancy agreement", "property", "landlord", "occupants", "rooms"],
    ),
    fields={
        "address": _f(KIND_TEXT, "property address"),
        "owner": _f(KIND_TEXT, "owner / landlord / tenant name"),
        "occupants": _f(KIND_INT, "number of occupants"),
        "size_rooms": _f(KIND_INT, "number of rooms / bedrooms"),
    },
)

CAS = DocumentProfile(
    type="cas",
    match=MatchSpec(
        keywords=["confirmation of acceptance for studies", "cas number", "confirmation of acceptance"],
    ),
    fields={
        "reference_no": _f(KIND_TEXT, "CAS reference number"),
        "sponsor": _f(KIND_TEXT, "sponsor institution"),
        "course": _f(KIND_TEXT, "course title"),
        "start_date": _f(KIND_DATE, "course start date"),
        "end_date": _f(KIND_DATE, "course end date"),
        "name": _f(KIND_TEXT, "student / applicant name"),
    },
)

COS = DocumentProfile(
    type="cos",
    match=MatchSpec(
        keywords=["certificate of sponsorship", "cos number", "sponsorship licence"],
    ),
    fields={
        "reference_no": _f(KIND_TEXT, "CoS reference number"),
        "sponsor": _f(KIND_TEXT, "sponsor employer"),
        "role": _f(KIND_TEXT, "job role / SOC code"),
        "start_date": _f(KIND_DATE, "employment start date"),
        "end_date": _f(KIND_DATE, "employment end date"),
        "name": _f(KIND_TEXT, "worker / applicant name"),
    },
)

RELATIONSHIP_EVIDENCE = DocumentProfile(
    type="relationship_evidence",
    match=MatchSpec(
        keywords=["relationship evidence", "photos", "correspondence",
                  "cohabitation", "communication log", "shared bills",
                  "genuine relationship"],
    ),
    fields={
        "parties": _f(KIND_TEXT, "the two people named"),
        "evidence_type": _f(KIND_TEXT, "type of evidence (photos, correspondence, …)"),
    },
)

GENERAL = DocumentProfile(
    type="general",
    match=MatchSpec(),
    fields={},  # free-text fallback: no typed fields
)

# Registry order matters: more specific / disambiguating profiles first. The
# type matcher scores all profiles and picks the max; this order only breaks
# ties in the deterministic fallback path (before any LLM disambiguation).
PROFILES: dict[str, DocumentProfile] = {
    p.type: p
    for p in (
        PASSPORT,
        BANK_STATEMENT,
        EMPLOYMENT_LETTER,
        PAYSLIP,
        INVITATION_LETTER,
        TB_CERTIFICATE,
        ENGLISH_TEST,
        MARRIAGE_CERTIFICATE,
        ACCOMMODATION,
        CAS,
        COS,
        RELATIONSHIP_EVIDENCE,
        GENERAL,
    )
}


def get_profile(doc_type: str) -> DocumentProfile:
    """Return the profile for a document type (falls back to ``general``)."""
    return PROFILES.get(doc_type, GENERAL)


def all_profiles() -> list[DocumentProfile]:
    """All profiles except the ``general`` fallback (matching candidates)."""
    return [p for p in PROFILES.values() if p.type != "general"]
