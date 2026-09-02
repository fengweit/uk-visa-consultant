"""Generate the demo/backtest corpus: visa applications x scenarios as real PDFs.

For each case: renders text-based and/or scanned (image-only) PDFs into
data/corpus/<visa>/<case_id>/ and writes a ground-truth case.json capturing the
scenario, client profile, document list (expected doc_type + scanned flag), and
the expected gap-analysis outcome.

Usage:
    uv run python scripts/generate_corpus.py [--out data/corpus] [--case <id>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

APP_DATE = "2026-09-01"


# ---------------------------------------------------------------------------
# Low-level renderers
# ---------------------------------------------------------------------------

def _text_pdf(path: Path, title: str, pairs: list[tuple[str, str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    _, h = A4
    y = h - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, y, title)
    y -= 34
    c.setFont("Helvetica", 11)
    for label, value in pairs:
        c.drawString(60, y, f"{label}: {value}")
        y -= 20
        if y < 70:
            c.showPage()
            y = h - 60
            c.setFont("Helvetica", 11)
    c.save()


def _scanned_pdf(path: Path, title: str, pairs: list[tuple[str, str]]) -> None:
    """Image-only PDF (no text layer) -> pdf-inspector classifies 'scanned'."""
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except TypeError:
        font = ImageFont.load_default(size=24)
    d.text((80, 90), title, fill="black", font=font)
    y = 170
    for label, value in pairs:
        d.text((80, y), f"{label}: {value}", fill="black", font=font)
        y += 45
    png = path.with_suffix(".png")
    img.save(png)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(str(png), 0, 0, width=A4[0], height=A4[1])
    c.save()
    png.unlink()


def _render(out_dir: Path, filename: str, title: str, pairs, scanned: bool) -> None:
    path = out_dir / filename
    (_scanned_pdf if scanned else _text_pdf)(path, title, pairs)


# ---------------------------------------------------------------------------
# Document builders (name -> {doc_type, build})
# ---------------------------------------------------------------------------

def build_passport(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "PASSPORT", [
        ("Full Name", d["name"]),
        ("Date of Birth", d["dob"]),
        ("Passport Number", d["passport_no"]),
        ("Nationality", d["nationality"]),
        ("Date of Expiry", d["expiry"]),
        ("Place of Birth", d.get("pob", "Shenzhen, China")),
        ("Issuing Authority", "MPS China"),
    ], scanned)


def build_bank_statement(out_dir, filename, scanned, **d):
    pairs = [
        ("Bank", d["bank"]),
        ("Account Holder", d["holder"]),
        ("Statement Period", f'{d["period_start"]} to {d["period_end"]}'),
        ("Account Number", d.get("account_no", "40293847120")),
        ("Sort Code", d.get("sort_code", "40-11-18")),
        ("Transactions", ""),
    ]
    for date, desc, amt in d["transactions"]:
        pairs.append((f"  {date}", f"{desc}  {amt:+,.2f}"))
    pairs.append(("Closing Balance", f'{d["closing_balance"]:,.2f}'))
    pairs.append(("Minimum Balance", f'{d["min_balance"]:,.2f}'))
    _render(out_dir, filename, "BANK STATEMENT", pairs, scanned)


def build_employment_letter(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "LETTER OF EMPLOYMENT", [
        ("Employer", d["employer"]),
        ("Employee", d["employee"]),
        ("Job Title", d["role"]),
        ("Annual Salary", f'{d["salary"]:,.2f}'),
        ("Start Date", d["start_date"]),
        ("Signed", "Yes" if d.get("signed", True) else "No"),
    ], scanned)


def build_cas(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "CONFIRMATION OF ACCEPTANCE FOR STUDIES (CAS)", [
        ("CAS Number", d["reference_no"]),
        ("Sponsor Institution", d["sponsor"]),
        ("Course Title", d["course"]),
        ("Course Start Date", d["start_date"]),
        ("Course End Date", d["end_date"]),
        ("Student Name", d["name"]),
    ], scanned)


def build_cos(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "CERTIFICATE OF SPONSORSHIP (COS)", [
        ("CoS Number", d["reference_no"]),
        ("Sponsoring Organisation", d["sponsor"]),
        ("Occupation Code", d["role"]),
        ("Commencement Date", d["start_date"]),
        ("Conclusion Date", d["end_date"]),
        ("Sponsored Worker", d["name"]),
    ], scanned)


def build_english_test(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "ENGLISH LANGUAGE TEST", [
        ("Candidate Name", d["name"]),
        ("Test", d["test"]),
        ("CEFR Level / Band", d["level"]),
        ("Test Date", d["date"]),
        ("Reference Number", d.get("reference_no", "REF-0000")),
    ], scanned)


def build_tb_certificate(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "TB TEST CERTIFICATE", [
        ("Applicant Name", d["name"]),
        ("Certificate Number", d["certificate_no"]),
        ("Clinic / Test Centre", d["clinic"]),
        ("Test Date", d["date"]),
        ("Result", d.get("result", "Clear")),
    ], scanned)


def build_marriage_certificate(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "MARRIAGE CERTIFICATE", [
        ("First Spouse", d["spouse_a"]),
        ("Second Spouse", d["spouse_b"]),
        ("Date of Marriage", d["date"]),
        ("Place of Marriage", d["place"]),
        ("Registration Number", d["registration_no"]),
    ], scanned)


def build_accommodation(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "ACCOMMODATION / TENANCY AGREEMENT", [
        ("Property Address", d["address"]),
        ("Landlord / Tenant", d["owner"]),
        ("Occupants", str(d["occupants"])),
        ("Rooms / Bedrooms", str(d["size_rooms"])),
    ], scanned)


def build_invitation_letter(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "INVITATION LETTER", [
        ("Inviter / Host", d["inviter"]),
        ("Invitee", d["invitee"]),
        ("Relationship", d["relationship"]),
        ("Address of Stay", d["address"]),
        ("Letter Date", d["date"]),
    ], scanned)


def build_itinerary(out_dir, filename, scanned, **d):
    _render(out_dir, filename, "TRAVEL ITINERARY", [
        ("Traveller", d["name"]),
        ("Arrival", d["arrival"]),
        ("Departure", d["departure"]),
        ("Flight", d.get("flight", "CZ303 / BA138")),
    ], scanned)


DOC_TYPES = {
    "passport": "passport",
    "bank_statement": "bank_statement",
    "employment_letter": "employment_letter",
    "cas": "cas",
    "cos": "cos",
    "english_test": "english_test",
    "tb_certificate": "tb_certificate",
    "marriage_certificate": "marriage_certificate",
    "accommodation": "accommodation",
    "invitation_letter": "invitation_letter",
    "itinerary": "general",
}

BUILDERS = {
    "passport": build_passport,
    "bank_statement": build_bank_statement,
    "employment_letter": build_employment_letter,
    "cas": build_cas,
    "cos": build_cos,
    "english_test": build_english_test,
    "tb_certificate": build_tb_certificate,
    "marriage_certificate": build_marriage_certificate,
    "accommodation": build_accommodation,
    "invitation_letter": build_invitation_letter,
    "itinerary": build_itinerary,
}


# ---------------------------------------------------------------------------
# Case definitions
# ---------------------------------------------------------------------------

_JANE = {"name": "Jane Doe", "dob": "1998-04-02", "nationality": "CN",
         "passport_no": "E12345678", "expiry": "2027-03-03"}


def _passport(client, scanned=False):
    return {"builder": "passport", "file": "passport.pdf", "scanned": scanned,
            "name": client["name"], "dob": client["dob"],
            "passport_no": client["passport_no"], "nationality": client["nationality"],
            "expiry": client["expiry"]}


def _bank(holder, closing, minbal, period=("2026-05-01", "2026-08-31"),
          tx=None, scanned=False):
    tx = tx or [("2026-06-01", "Salary", 5000.00), ("2026-07-01", "Salary", 5000.00),
                ("2026-08-01", "Salary", 5000.00)]
    return {"builder": "bank_statement", "file": "bank_statement.pdf", "scanned": scanned,
            "bank": "HSBC UK", "holder": holder, "period_start": period[0],
            "period_end": period[1], "transactions": tx,
            "closing_balance": closing, "min_balance": minbal}


def _employment(employer, employee, role, salary, start="2022-05-01", signed=True):
    return {"builder": "employment_letter", "file": "employment_letter.pdf",
            "employer": employer, "employee": employee, "role": role,
            "salary": salary, "start_date": start, "signed": signed}


def _english(name, test="IELTS", level="B1", date="2026-03-15"):
    return {"builder": "english_test", "file": "english_test.pdf", "name": name,
            "test": test, "level": level, "date": date, "reference_no": "REF-0042"}


def _tb(name, cert="TB-2026-0091", date="2026-06-01"):
    return {"builder": "tb_certificate", "file": "tb_certificate.pdf", "name": name,
            "certificate_no": cert, "clinic": "Shenzhen IOM Clinic", "date": date,
            "result": "Clear"}


def _accommodation(address, owner, occupants=1, rooms=1):
    return {"builder": "accommodation", "file": "accommodation.pdf", "address": address,
            "owner": owner, "occupants": occupants, "size_rooms": rooms}


def _invitation(inviter, invitee, relationship, address, date="2026-06-20"):
    return {"builder": "invitation_letter", "file": "invitation.pdf", "inviter": inviter,
            "invitee": invitee, "relationship": relationship, "address": address, "date": date}


def _marriage(a, b, date="2024-05-18", place="Shenzhen, China", reg="M-2024-0771"):
    return {"builder": "marriage_certificate", "file": "marriage_certificate.pdf",
            "spouse_a": a, "spouse_b": b, "date": date, "place": place,
            "registration_no": reg}


def _itinerary(name, arrival, departure):
    return {"builder": "itinerary", "file": "itinerary.pdf", "name": name,
            "arrival": arrival, "departure": departure}


CASES: list[dict] = []

# --- Visitor ---
CASES += [
    {
        "case_id": "visitor_001_complete", "visa_type": "visitor", "route": "Standard Visitor",
        "scenario": "complete",
        "description": "All required documents present and valid -> READY.",
        "client": dict(_JANE, country_of_residence="CN"),
        "documents": [
            _passport(_JANE),
            _bank("Jane Doe", 8500.00, 3200.00),
            _employment("Acme Ltd", "Jane Doe", "Software Engineer", 62000.00),
            _accommodation("Premier Inn, 10 King St, London", "Premier Inn (booking)", 1, 1),
            _invitation("John Smith", "Jane Doe", "Friend", "12 Oak Road, Manchester"),
            _itinerary("Jane Doe", "2026-09-20", "2026-10-05"),
        ],
        "expected": {"status": "READY", "gap_items": []},
    },
    {
        "case_id": "visitor_002_missing_funds", "visa_type": "visitor", "route": "Standard Visitor",
        "scenario": "missing_funds",
        "description": "No bank statement supplied -> funds requirement MISSING.",
        "client": dict(_JANE, country_of_residence="CN"),
        "documents": [
            _passport(_JANE),
            _employment("Acme Ltd", "Jane Doe", "Software Engineer", 62000.00),
            _accommodation("Premier Inn, London", "Premier Inn (booking)", 1, 1),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "visitor.funds", "verdict": "MISSING", "reason": "no proof of funds supplied"}]},
    },
    {
        "case_id": "visitor_003_name_mismatch", "visa_type": "visitor", "route": "Standard Visitor",
        "scenario": "name_mismatch",
        "description": "Bank account holder name differs from passport -> INCONSISTENT.",
        "client": dict(_JANE, country_of_residence="CN"),
        "documents": [
            _passport(_JANE),
            _bank("Jane A. Doe", 8500.00, 3200.00),   # mismatch vs passport "Jane Doe"
            _employment("Acme Ltd", "Jane Doe", "Software Engineer", 62000.00),
            _accommodation("Premier Inn, London", "Premier Inn (booking)", 1, 1),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "visitor.funds", "verdict": "INCONSISTENT",
             "reason": "bank account holder 'Jane A. Doe' != passport 'Jane Doe'"}]},
    },
    {
        "case_id": "visitor_004_passport_expiring", "visa_type": "visitor", "route": "Standard Visitor",
        "scenario": "passport_expiring",
        "description": "Passport expires during the intended stay -> EXPIRING.",
        "client": dict(_JANE, country_of_residence="CN"),
        "documents": [
            _passport({**_JANE, "expiry": "2026-09-25"}),  # expires mid-stay (20 Sep - 5 Oct)
            _bank("Jane Doe", 8500.00, 3200.00),
            _employment("Acme Ltd", "Jane Doe", "Software Engineer", 62000.00),
            _accommodation("Premier Inn, London", "Premier Inn (booking)", 1, 1),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "visitor.passport", "verdict": "EXPIRING",
             "reason": "passport expires 2026-09-25 before stay end 2026-10-05"}]},
    },
    {
        "case_id": "visitor_005_scanned_passport", "visa_type": "visitor", "route": "Standard Visitor",
        "scenario": "scanned_document",
        "description": "Passport supplied as an image-only (scanned) PDF -> needs OCR routing.",
        "client": dict(_JANE, country_of_residence="CN"),
        "documents": [
            _passport(_JANE, scanned=True),
            _bank("Jane Doe", 8500.00, 3200.00),
            _employment("Acme Ltd", "Jane Doe", "Software Engineer", 62000.00),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "visitor.passport", "verdict": "INVALID",
             "reason": "scanned PDF, no text layer -> OCR routing required"}]},
    },
]

# --- Student ---
_STU_CLIENT = dict(_JANE, country_of_residence="CN")
CASES += [
    {
        "case_id": "student_001_complete", "visa_type": "student", "route": "Student Route",
        "scenario": "complete",
        "description": "All required documents present and valid -> READY.",
        "client": _STU_CLIENT,
        "documents": [
            _passport(_STU_CLIENT),
            {"builder": "cas", "file": "cas.pdf",
             "reference_no": "S1234567890", "sponsor": "University of Manchester",
             "course": "MSc Computer Science", "start_date": "2026-09-21",
             "end_date": "2027-09-20", "name": "Jane Doe"},
            _bank("Jane Doe", 18420.00, 15200.00),
            _english("Jane Doe", "IELTS", "7.0", "2026-03-15"),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "READY", "gap_items": []},
    },
    {
        "case_id": "student_002_missing_cas", "visa_type": "student", "route": "Student Route",
        "scenario": "missing_cas",
        "description": "CAS not supplied -> mandatory CAS MISSING.",
        "client": _STU_CLIENT,
        "documents": [
            _passport(_STU_CLIENT),
            _bank("Jane Doe", 18420.00, 15200.00),
            _english("Jane Doe", "IELTS", "7.0", "2026-03-15"),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "student.cas", "verdict": "MISSING", "reason": "CAS not supplied"}]},
    },
    {
        "case_id": "student_003_funds_insufficient", "visa_type": "student", "route": "Student Route",
        "scenario": "funds_insufficient",
        "description": "Closing balance below required maintenance -> INVALID.",
        "client": _STU_CLIENT,
        "documents": [
            _passport(_STU_CLIENT),
            {"builder": "cas", "file": "cas.pdf",
             "reference_no": "S1234567890", "sponsor": "University of Manchester",
             "course": "MSc Computer Science", "start_date": "2026-09-21",
             "end_date": "2027-09-20", "name": "Jane Doe"},
            _bank("Jane Doe", 8000.00, 7500.00),  # below £10,230 maintenance
            _english("Jane Doe", "IELTS", "7.0", "2026-03-15"),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "student.funds.28day", "verdict": "INVALID",
             "reason": "closing balance £8,000 below required maintenance"}]},
    },
    {
        "case_id": "student_004_funds_28day_violation", "visa_type": "student", "route": "Student Route",
        "scenario": "funds_28day_violation",
        "description": "Balance dips below minimum during the 28-day hold -> INVALID.",
        "client": _STU_CLIENT,
        "documents": [
            _passport(_STU_CLIENT),
            {"builder": "cas", "file": "cas.pdf",
             "reference_no": "S1234567890", "sponsor": "University of Manchester",
             "course": "MSc Computer Science", "start_date": "2026-09-21",
             "end_date": "2027-09-20", "name": "Jane Doe"},
            _bank("Jane Doe", 15000.00, 2000.00, tx=[
                ("2026-06-01", "Opening", 10000.00),
                ("2026-07-01", "Large withdrawal", -8000.00),
                ("2026-07-02", "Deposit", 13000.00),
                ("2026-08-01", "Salary", 5000.00),
            ]),  # min balance £2,000 -> 28-day hold violated
            _english("Jane Doe", "IELTS", "7.0", "2026-03-15"),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "student.funds.28day", "verdict": "INVALID",
             "reason": "minimum balance £2,000 broke the 28-day hold"}]},
    },
    {
        "case_id": "student_005_name_mismatch", "visa_type": "student", "route": "Student Route",
        "scenario": "name_mismatch",
        "description": "CAS student name differs from passport -> INCONSISTENT.",
        "client": _STU_CLIENT,
        "documents": [
            _passport(_STU_CLIENT),
            {"builder": "cas", "file": "cas.pdf",
             "reference_no": "S1234567890", "sponsor": "University of Manchester",
             "course": "MSc Computer Science", "start_date": "2026-09-21",
             "end_date": "2027-09-20", "name": "Jane A. Doe"},  # mismatch
            _bank("Jane Doe", 18420.00, 15200.00),
            _english("Jane Doe", "IELTS", "7.0", "2026-03-15"),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "student.cas", "verdict": "INCONSISTENT",
             "reason": "CAS name 'Jane A. Doe' != passport 'Jane Doe'"}]},
    },
]

# --- Worker ---
_WORK_CLIENT = dict(_JANE, country_of_residence="CN")
CASES += [
    {
        "case_id": "worker_001_complete", "visa_type": "worker", "route": "Skilled Worker",
        "scenario": "complete",
        "description": "All required documents present and valid -> READY.",
        "client": _WORK_CLIENT,
        "documents": [
            _passport(_WORK_CLIENT),
            {"builder": "cos", "file": "cos.pdf",
             "reference_no": "C9876543210", "sponsor": "TechCorp UK",
             "role": "Software Engineer (SOC 2135)", "start_date": "2026-10-01",
             "end_date": "2029-09-30", "name": "Jane Doe"},
            _english("Jane Doe", "IELTS", "B1", "2026-02-10"),
            _bank("Jane Doe", 5000.00, 4800.00),  # >= £1,270 maintenance
            _tb("Jane Doe"),
        ],
        "expected": {"status": "READY", "gap_items": []},
    },
    {
        "case_id": "worker_002_missing_cos", "visa_type": "worker", "route": "Skilled Worker",
        "scenario": "missing_cos",
        "description": "CoS not supplied -> mandatory CoS MISSING.",
        "client": _WORK_CLIENT,
        "documents": [
            _passport(_WORK_CLIENT),
            _english("Jane Doe", "IELTS", "B1", "2026-02-10"),
            _bank("Jane Doe", 5000.00, 4800.00),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "worker.cos", "verdict": "MISSING", "reason": "CoS not supplied"}]},
    },
    {
        "case_id": "worker_003_funds_insufficient", "visa_type": "worker", "route": "Skilled Worker",
        "scenario": "funds_insufficient",
        "description": "Closing balance below £1,270 maintenance -> INVALID.",
        "client": _WORK_CLIENT,
        "documents": [
            _passport(_WORK_CLIENT),
            {"builder": "cos", "file": "cos.pdf",
             "reference_no": "C9876543210", "sponsor": "TechCorp UK",
             "role": "Software Engineer (SOC 2135)", "start_date": "2026-10-01",
             "end_date": "2029-09-30", "name": "Jane Doe"},
            _english("Jane Doe", "IELTS", "B1", "2026-02-10"),
            _bank("Jane Doe", 900.00, 850.00),  # below £1,270
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "worker.funds", "verdict": "INVALID",
             "reason": "closing balance £900 below £1,270 maintenance"}]},
    },
    {
        "case_id": "worker_004_missing_english", "visa_type": "worker", "route": "Skilled Worker",
        "scenario": "missing_english",
        "description": "English evidence not supplied -> MISSING.",
        "client": _WORK_CLIENT,
        "documents": [
            _passport(_WORK_CLIENT),
            {"builder": "cos", "file": "cos.pdf",
             "reference_no": "C9876543210", "sponsor": "TechCorp UK",
             "role": "Software Engineer (SOC 2135)", "start_date": "2026-10-01",
             "end_date": "2029-09-30", "name": "Jane Doe"},
            _bank("Jane Doe", 5000.00, 4800.00),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "worker.english", "verdict": "MISSING", "reason": "no English evidence supplied"}]},
    },
    {
        "case_id": "worker_005_name_mismatch", "visa_type": "worker", "route": "Skilled Worker",
        "scenario": "name_mismatch",
        "description": "CoS worker name differs from passport -> INCONSISTENT.",
        "client": _WORK_CLIENT,
        "documents": [
            _passport(_WORK_CLIENT),
            {"builder": "cos", "file": "cos.pdf",
             "reference_no": "C9876543210", "sponsor": "TechCorp UK",
             "role": "Software Engineer (SOC 2135)", "start_date": "2026-10-01",
             "end_date": "2029-09-30", "name": "Janet Doe"},  # mismatch
            _english("Jane Doe", "IELTS", "B1", "2026-02-10"),
            _bank("Jane Doe", 5000.00, 4800.00),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "worker.cos", "verdict": "INCONSISTENT",
             "reason": "CoS name 'Janet Doe' != passport 'Jane Doe'"}]},
    },
]

# --- Spouse ---
_SPOUSE_APPLICANT = dict(_JANE, country_of_residence="CN")
_SPONSOR = "David Roe"
CASES += [
    {
        "case_id": "spouse_001_complete", "visa_type": "spouse", "route": "Spouse / Partner",
        "scenario": "complete",
        "description": "All required documents present and valid -> READY.",
        "client": _SPOUSE_APPLICANT,
        "documents": [
            _passport(_SPOUSE_APPLICANT),
            _marriage("Jane Doe", _SPONSOR),
            _employment("Roe Consulting Ltd", _SPONSOR, "Consultant", 35000.00),
            _bank(_SPONSOR, 12000.00, 9000.00),
            _english("Jane Doe", "IELTS", "A1", "2026-04-10"),
            _accommodation("22 Cedar Lane, Leeds", _SPONSOR, 2, 2),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "READY", "gap_items": []},
    },
    {
        "case_id": "spouse_002_income_below_threshold", "visa_type": "spouse", "route": "Spouse / Partner",
        "scenario": "income_below_threshold",
        "description": "Sponsor income below minimum requirement -> INVALID.",
        "client": _SPOUSE_APPLICANT,
        "documents": [
            _passport(_SPOUSE_APPLICANT),
            _marriage("Jane Doe", _SPONSOR),
            _employment("Roe Consulting Ltd", _SPONSOR, "Consultant", 20000.00),  # < £29,000
            _bank(_SPONSOR, 6000.00, 4500.00),
            _english("Jane Doe", "IELTS", "A1", "2026-04-10"),
            _accommodation("22 Cedar Lane, Leeds", _SPONSOR, 2, 2),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "spouse.financial.income", "verdict": "INVALID",
             "reason": "sponsor income £20,000 below minimum requirement"}]},
    },
    {
        "case_id": "spouse_003_missing_english", "visa_type": "spouse", "route": "Spouse / Partner",
        "scenario": "missing_english",
        "description": "English evidence not supplied -> MISSING.",
        "client": _SPOUSE_APPLICANT,
        "documents": [
            _passport(_SPOUSE_APPLICANT),
            _marriage("Jane Doe", _SPONSOR),
            _employment("Roe Consulting Ltd", _SPONSOR, "Consultant", 35000.00),
            _bank(_SPONSOR, 12000.00, 9000.00),
            _accommodation("22 Cedar Lane, Leeds", _SPONSOR, 2, 2),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "spouse.english", "verdict": "MISSING", "reason": "no English evidence supplied"}]},
    },
    {
        "case_id": "spouse_004_weak_relationship", "visa_type": "spouse", "route": "Spouse / Partner",
        "scenario": "weak_relationship_evidence",
        "description": "Only a marriage certificate; no genuine-relationship evidence -> INCOMPLETE.",
        "client": _SPOUSE_APPLICANT,
        "documents": [
            _passport(_SPOUSE_APPLICANT),
            _marriage("Jane Doe", _SPONSOR),   # no photos/correspondence/cohabitation
            _employment("Roe Consulting Ltd", _SPONSOR, "Consultant", 35000.00),
            _bank(_SPONSOR, 12000.00, 9000.00),
            _english("Jane Doe", "IELTS", "A1", "2026-04-10"),
            _accommodation("22 Cedar Lane, Leeds", _SPONSOR, 2, 2),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "spouse.genuine", "verdict": "MISSING",
             "reason": "no evidence the relationship is genuine and subsisting"}]},
    },
    {
        "case_id": "spouse_005_name_mismatch", "visa_type": "spouse", "route": "Spouse / Partner",
        "scenario": "name_mismatch",
        "description": "Marriage certificate name differs from passport -> INCONSISTENT.",
        "client": _SPOUSE_APPLICANT,
        "documents": [
            _passport(_SPOUSE_APPLICANT),
            _marriage("Janet Doe", _SPONSOR),  # mismatch vs passport "Jane Doe"
            _employment("Roe Consulting Ltd", _SPONSOR, "Consultant", 35000.00),
            _bank(_SPONSOR, 12000.00, 9000.00),
            _english("Jane Doe", "IELTS", "A1", "2026-04-10"),
            _accommodation("22 Cedar Lane, Leeds", _SPONSOR, 2, 2),
            _tb("Jane Doe"),
        ],
        "expected": {"status": "INCOMPLETE", "gap_items": [
            {"req_id": "spouse.relationship", "verdict": "INCONSISTENT",
             "reason": "marriage cert 'Janet Doe' != passport 'Jane Doe'"}]},
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(out_dir: Path, only_case: str | None = None) -> None:
    for case in CASES:
        if only_case and case["case_id"] != only_case:
            continue
        case_dir = out_dir / case["visa_type"] / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)

        docs_meta = []
        for d in case["documents"]:
            builder = d["builder"]
            scanned = d.get("scanned", False)
            filename = d["file"]
            kwargs = {k: v for k, v in d.items() if k not in ("builder", "file", "scanned")}
            BUILDERS[builder](case_dir, filename, scanned, **kwargs)
            docs_meta.append({"file": filename, "doc_type": DOC_TYPES[builder],
                              "scanned": scanned})

        meta = {
            "case_id": case["case_id"],
            "visa_type": case["visa_type"],
            "route": case["route"],
            "scenario": case["scenario"],
            "description": case["description"],
            "application_date": APP_DATE,
            "client": case["client"],
            "documents": docs_meta,
            "expected": case["expected"],
        }
        (case_dir / "case.json").write_text(json.dumps(meta, indent=2))

    n = len(CASES) if not only_case else 1
    print(f"generated {n} case(s) under {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/corpus")
    ap.add_argument("--case", default=None)
    args = ap.parse_args()
    generate(Path(args.out), args.case)
