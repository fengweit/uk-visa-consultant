"""Intake agent: routing a Message through intent -> intake (no network)."""
from reportlab.pdfgen import canvas

from uk_visa_consultant.agent import IntakeAgent
from uk_visa_consultant.models import Attachment, Channel, Message


def _passport_pdf(path):
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "PASSPORT")
    c.drawString(72, 700, "Full Name: Jane Doe")
    c.drawString(72, 680, "Passport Number: E12345678")
    c.drawString(72, 660, "Date of Birth: 1998-04-02")
    c.drawString(72, 640, "Nationality: Chinese")
    c.drawString(72, 620, "Date of Expiry: 2027-03-03")
    c.save()


def _msg(body, attachments=None):
    return Message(id="m1", client_id="c1", channel=Channel.LOCAL, body=body,
                   attachments=attachments or [])


def test_submit_document_with_attachment_parses(tmp_path):
    p = tmp_path / "passport.pdf"
    _passport_pdf(p)
    msg = _msg("here is my passport", [
        Attachment(kind="pdf", local_path=str(p), mime="application/pdf"),
    ])
    result = IntakeAgent().handle(msg)
    assert result.action == "parse_document"
    assert result.documents[0].type == "passport"
    assert "passport" in result.reply


def test_submit_document_without_attachment_requests_one():
    result = IntakeAgent().handle(_msg("I'm sending you my passport"))
    assert result.action == "request_document"
    assert result.documents == []


def test_escalate_human():
    result = IntakeAgent().handle(_msg("I want to speak to a human"))
    assert result.escalation is True
    assert result.action == "escalate"


def test_document_query_answers():
    result = IntakeAgent().handle(_msg("what documents do I need?"))
    assert result.action == "answer_query"
    assert "passport" in result.reply
