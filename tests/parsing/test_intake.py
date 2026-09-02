"""Tests for the document-parsing intake path (docs/specs/document-parsing.md)."""
from __future__ import annotations

import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from uk_visa_consultant.llm import StubLLMClient
from uk_visa_consultant.models import Document, FieldProvenance
from uk_visa_consultant.parsing import extract, extract_pdf, intake, match_type


# --- synthetic PDF builders --------------------------------------------------

def _text_pdf(path, pages):
    c = canvas.Canvas(str(path), pagesize=A4)
    for i, lines in enumerate(pages):
        y = 780
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        if i < len(pages) - 1:
            c.showPage()
    c.save()
    return path


@pytest.fixture
def bank_pdf(tmp_path):
    return _text_pdf(tmp_path / "statement.pdf", [
        [
            "HSBC UK - Bank Statement",
            "Statement of Account",
            "Account Holder: Jane Doe",
            "Account Number: 12345678   Sort Code: 40-12-34",
            "Statement Period: 2026-05-01 to 2026-07-31",
            "Closing Balance: 18420.55",
            "Minimum Balance in Period: 15200.00",
        ],
        [
            "Transactions",
            "01 May 2026   GROCERY   -45.20",
            "01 Jun 2026   SALARY    2500.00",
        ],
    ])


@pytest.fixture
def passport_pdf(tmp_path):
    return _text_pdf(tmp_path / "passport.pdf", [[
        "PASSPORT",
        "Passport Number: 123456789",
        "Full Name: JOHN SMITH",
        "Date of Birth: 1990-01-15",
        "Date of Expiry: 2030-06-30",
        "Nationality: BRITISH",
        "Place of Birth: LONDON",
    ]])


@pytest.fixture
def scanned_pdf(tmp_path):
    img = Image.new("RGB", (400, 600), "white")
    px = img.load()
    for x in range(0, 400, 8):
        for y in range(0, 600, 8):
            px[x, y] = (0, 0, 0)
    png = tmp_path / "scan.png"
    img.save(str(png))
    p = tmp_path / "scanned.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    c.drawImage(str(png), 100, 100, width=400, height=600)
    c.showPage()
    c.save()
    return p


@pytest.fixture
def unknown_pdf(tmp_path):
    return _text_pdf(tmp_path / "receipt.pdf", [[
        "Purchase Receipt",
        "Item: Notebook",
        "Total: 4.50",
        "Thank you for your purchase",
    ]])


BANK_VALUES = {
    "account_holder": "Jane Doe",
    "period_start": "2026-05-01",
    "period_end": "2026-07-31",
    "closing_balance": 18420.55,
    "min_balance": 15200.0,
}

PASSPORT_VALUES = {
    "full_name": "JOHN SMITH",
    "dob": "1990-01-15",
    "passport_no": "123456789",
    "expiry": "2030-06-30",
    "nationality": "BRITISH",
}


# --- typed field extraction ---------------------------------------------------

def test_bank_statement_fields(bank_pdf):
    stub = StubLLMClient({"bank_statement": dict(BANK_VALUES)})
    doc = intake(bank_pdf, "application/pdf", llm=stub)

    assert isinstance(doc, Document)
    assert doc.type == "bank_statement"
    assert doc.fields == BANK_VALUES
    assert doc.quality.scanned is False
    assert doc.quality.ocr_used is False
    assert doc.source_pages == [1, 2]


def test_passport_fields(passport_pdf):
    stub = StubLLMClient({"passport": dict(PASSPORT_VALUES)})
    doc = intake(passport_pdf, "application/pdf", llm=stub)

    assert doc.type == "passport"
    assert doc.fields == PASSPORT_VALUES
    assert doc.quality.scanned is False


# --- provenance ----------------------------------------------------------------

def test_provenance_present_on_extracted_fields(bank_pdf):
    stub = StubLLMClient({"bank_statement": dict(BANK_VALUES)})
    doc = intake(bank_pdf, "application/pdf", llm=stub)

    for field in BANK_VALUES:
        assert field in doc.provenance
        assert isinstance(doc.provenance[field], FieldProvenance)

    # values that appear verbatim in the source resolve to page 1 at high confidence
    assert doc.provenance["closing_balance"].page == 1
    assert doc.provenance["closing_balance"].region == "text"
    assert doc.provenance["closing_balance"].confidence == 0.97


# --- scanned / image-only detection -------------------------------------------

def test_scanned_image_only_pdf_is_not_empty_text(scanned_pdf):
    doc = intake(scanned_pdf, "application/pdf", llm=StubLLMClient())

    assert doc.quality.scanned is True
    assert doc.quality.ocr_used is False  # OCR out of scope
    assert doc.type == "general"  # no text layer -> nothing to match on
    assert doc.fields == {}
    assert doc.source_pages == [1]
    assert any(f.startswith("needs_ocr:") for f in doc.flags)
    assert "low_quality" in doc.flags


# --- unknown documents ---------------------------------------------------------

def test_unknown_document_types_to_general(unknown_pdf):
    doc = intake(unknown_pdf, "application/pdf", llm=StubLLMClient())

    assert doc.type == "general"
    assert doc.fields == {}
    assert doc.provenance == {}
    assert doc.quality.scanned is False


# --- fail-closed on malformed model output --------------------------------------

def test_fail_closed_on_malformed_model_output(bank_pdf):
    stub = StubLLMClient({"bank_statement": {"closing_balance": "not-a-number"}})
    doc = intake(bank_pdf, "application/pdf", llm=stub)

    # schema validation failed -> deterministic "Label: Value" fallback reads the
    # values straight from the document text (never guessed/fabricated)
    assert "schema_validation_failed" in doc.flags
    assert "deterministic_fallback" in doc.flags
    assert doc.fields["closing_balance"] == 18420.55   # from the text
    assert doc.fields["account_holder"] == "Jane Doe"  # from the text
    # a label the fallback does not recognize stays null (fail closed)
    assert doc.fields["min_balance"] is None
    assert doc.provenance["min_balance"].region == "unfilled"


# --- deterministic type matching (no LLM) --------------------------------------

def test_type_matching_is_deterministic_without_llm(bank_pdf, passport_pdf, unknown_pdf):
    assert match_type(extract_pdf(bank_pdf)).type == "bank_statement"
    assert match_type(extract_pdf(passport_pdf)).type == "passport"
    assert match_type(extract_pdf(unknown_pdf)).type == "general"


def test_extract_text_file_dispatch(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("HSBC UK Bank Statement\nAccount Holder: Jane Doe\n", encoding="utf-8")
    ext = extract(p, "text/plain")
    assert ext.num_pages == 1
    assert ext.pages[0].has_text is True
    assert "Jane Doe" in ext.full_text
