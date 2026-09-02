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


def _email(from_addr, subject, body, attachment=None, mid="<e2e@x>", references=None):
    m = EmailMessage()
    m["From"] = from_addr
    m["To"] = "visa@example.com"
    m["Subject"] = subject
    m["Message-ID"] = mid
    if references:
        m["References"] = references
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
    r1 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my passport", p, "<b@x>", references="<a@x>")))
    assert "CAS" in r1.body and "funds" in r1.body.lower()  # both still missing
    assert r1.body.startswith("Thanks for sending your passport. I've checked it.")
    assert "making good progress" in r1.body.lower()
    assert "same thread" in r1.body.lower()

    b = tmp_path / "bank.pdf"
    _bank(b)
    r2 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my bank statement", b, "<c@x>", references="<a@x>")))
    assert "CAS" in r2.body and "funds" not in r2.body.lower()  # funds resolved, CAS missing

    c = tmp_path / "cas.pdf"
    _cas(c)
    r3 = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my cas", c, "<d@x>", references="<a@x>")))
    assert "ready to submit" in r3.body.lower()
    assert "good news" in r3.body.lower()
    assert r3.body.startswith("Thanks for sending your cas. I've checked it.")


def test_email_pdf_insufficient_funds_reports_invalid(tmp_path):
    adapter = _adapter(tmp_path)
    gw = Gateway()
    gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a student visa", mid="<a@x>")))
    b = tmp_path / "bank.pdf"
    _bank(b, closing="8000.00", minbal="7500.00")
    r = gw.handle(adapter.receive_email(_email("client@example.com", "s", "here is my bank statement", b, "<b@x>", references="<a@x>")))
    assert "below" in r.body.lower()


def test_same_email_two_threads_are_isolated(tmp_path):
    adapter = _adapter(tmp_path)
    gw = Gateway()

    # thread A: student
    gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a student visa", mid="<A1@x>")))
    # thread B: spouse — same email, NEW thread
    rB = gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a spouse visa", mid="<B1@x>")))
    assert "Spouse" in rB.body and "Student" not in rB.body

    p = tmp_path / "passport.pdf"
    _passport(p)

    # reply in thread A (References -> A1 root): submit passport -> student gaps
    rA = gw.handle(adapter.receive_email(
        _email("client@example.com", "s", "here is my passport", p, "<A2@x>", references="<A1@x>")))
    assert "CAS" in rA.body and "funds" in rA.body.lower()

    # reply in thread B (References -> B1 root): submit passport -> spouse gaps (no CAS)
    rB2 = gw.handle(adapter.receive_email(
        _email("client@example.com", "s", "here is my passport", p, "<B2@x>", references="<B1@x>")))
    assert "CAS" not in rB2.body


def test_multiple_attachments_in_one_email(tmp_path):
    adapter = _adapter(tmp_path)
    gw = Gateway()
    gw.handle(adapter.receive_email(_email("client@example.com", "s", "I want a student visa", mid="<a@x>")))

    p = tmp_path / "passport.pdf"
    _passport(p)
    b = tmp_path / "bank.pdf"
    _bank(b)

    # one email with TWO PDFs attached (plural phrasing)
    from email.message import EmailMessage
    m = EmailMessage()
    m["From"] = "client@example.com"
    m["To"] = "visa@example.com"
    m["Subject"] = "s"
    m["Message-ID"] = "<b@x>"
    m["References"] = "<a@x>"
    m.set_content("here are my documents")
    for path in (p, b):
        m.add_attachment(path.read_bytes(), maintype="application", subtype="pdf", filename=path.name)

    msg = adapter.receive_email(m.as_bytes())
    assert len(msg.attachments) == 2  # both files parsed
    reply = gw.handle(msg)
    # both parsed -> funds resolved, only CAS still missing (and it lists all missing)
    assert "CAS" in reply.body
    assert "funds" not in reply.body.lower()
    assert reply.body.startswith("Thanks for sending your bank statement, passport. I've checked them.")
    assert "making good progress" in reply.body.lower()
