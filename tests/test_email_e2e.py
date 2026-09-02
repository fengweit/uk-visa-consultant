"""Email-with-attachment E2E: real MIME + real PDFs through the full pipeline.

Builds genuine multipart emails with PDF attachments, feeds them through
EmailAdapter.receive_email → Gateway.handle, and asserts the agent's replies
carry the CORRECT gap analysis at every step. No live credentials (deterministic).
"""
from datetime import date, timedelta
from email.message import EmailMessage

from reportlab.pdfgen import canvas

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.gateway.loop import Gateway


def _pdf(path, lines):
    c = canvas.Canvas(str(path))
    y = 780
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()


def _email(from_addr, subject, body, attachment=None, mid="<e2e@x>"):
    m = EmailMessage()
    m["From"] = from_addr
    m["To"] = "visa@example.com"
    m["Subject"] = subject
    m["Message-ID"] = mid
    m.set_content(body)
    if attachment:
        m.add_attachment(attachment.read_bytes(), maintype="application",
                         subtype="pdf", filename=attachment.name)
    return m.as_bytes()


def _passport(path):
    _pdf(path, ["PASSPORT", "Full Name: Jane Doe", "Passport Number: E12345678",
                "Date of Birth: 1998-04-02", "Nationality: Chinese",
                "Date of Expiry: 2027-03-03"])


def _bank(path, closing="18420.55", minbal="15200.00"):
    end = (date.today() - timedelta(days=1)).isoformat()
    start = (date.today() - timedelta(days=92)).isoformat()
    _pdf(path, ["BANK STATEMENT", "Account Holder: Jane Doe",
                f"Statement Period: {start} to {end}",
                f"Closing Balance: {closing}", f"Minimum Balance: {minbal}"])


def _cas(path):
    _pdf(path, ["CONFIRMATION OF ACCEPTANCE FOR STUDIES (CAS)", "CAS Number: S1234567890",
                "Sponsor Institution: University of Manchester", "Course Title: MSc CS",
                "Course Start Date: 2026-09-21", "Course End Date: 2027-09-20",
                "Student Name: Jane Doe"])


def _adapter(tmp_path):
    return EmailAdapter(imap_host="x", imap_user="u", imap_password="p",
                        from_addr="visa@example.com", seen_path=tmp_path / "seen.json")


def test_email_pdf_conversation_progresses_to_ready(tmp_path):
    adapter = _adapter(tmp_path)
    gw = Gateway()
    gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a student visa", mid="<a@x>")))

    p = tmp_path / "passport.pdf"
    _passport(p)
    r1 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my passport", p, "<b@x>")))
    assert "CAS" in r1.body and "funds" in r1.body.lower()  # both still missing

    b = tmp_path / "bank.pdf"
    _bank(b)
    r2 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my bank statement", b, "<c@x>")))
    assert "CAS" in r2.body and "funds" not in r2.body.lower()  # funds resolved, CAS missing

    c = tmp_path / "cas.pdf"
    _cas(c)
    r3 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my cas", c, "<d@x>")))
    assert "ready to submit" in r3.body.lower()


def test_email_pdf_insufficient_funds_reports_invalid(tmp_path):
    adapter = _adapter(tmp_path)
    gw = Gateway()
    gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a student visa", mid="<a@x>")))
    b = tmp_path / "bank.pdf"
    _bank(b, closing="8000.00", minbal="7500.00")
    r = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my bank statement", b, "<b@x>")))
    assert "below" in r.body.lower()
