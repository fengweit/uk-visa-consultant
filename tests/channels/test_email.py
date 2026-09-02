"""Email adapter tests: MIME parsing, identity mapping, and SMTP send (aiosmtpd)."""
import socket
from email.message import EmailMessage
from pathlib import Path

from aiosmtpd.controller import Controller

from uk_visa_consultant.channels.email import EmailAdapter, parse_email
from uk_visa_consultant.models import Channel, Message


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_email(
    body: str = "here is my passport",
    attachment_name: str = "passport.pdf",
    attachment_data: bytes = b"%PDF-1.4 fake pdf bytes",
    attachment_mime: str = "application/pdf",
    from_addr: str = "Client <client@example.com>",
    message_id: str = "<abc123@example.com>",
) -> bytes:
    maintype, _, subtype = attachment_mime.partition("/")
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = "consultant@example.com"
    msg["Subject"] = "my documents"
    msg["Message-ID"] = message_id
    msg.set_content(body)
    msg.add_attachment(attachment_data, maintype=maintype, subtype=subtype, filename=attachment_name)
    return msg.as_bytes()


def test_parse_email_extracts_body_and_attachment():
    parsed = parse_email(_make_email())
    assert parsed.body == "here is my passport"
    assert parsed.from_addr == "client@example.com"
    assert parsed.message_id == "<abc123@example.com>"
    assert len(parsed.attachments) == 1
    name, mime, payload = parsed.attachments[0]
    assert name == "passport.pdf"
    assert mime == "application/pdf"
    assert payload == b"%PDF-1.4 fake pdf bytes"


def test_receive_email_maps_to_message_with_attachment_on_disk(tmp_path):
    adapter = EmailAdapter(upload_dir=tmp_path)
    message = adapter.receive_email(_make_email())

    assert message is not None
    assert message.channel is Channel.EMAIL
    assert message.body == "here is my passport"
    assert message.client_id  # resolved from From address

    assert len(message.attachments) == 1
    att = message.attachments[0]
    assert att.kind == "pdf"
    assert att.mime == "application/pdf"
    assert Path(att.local_path).exists()
    assert str(tmp_path) in att.local_path


def test_receive_email_dedups_by_message_id(tmp_path):
    adapter = EmailAdapter(upload_dir=tmp_path)
    raw = _make_email()
    first = adapter.receive_email(raw)
    second = adapter.receive_email(raw)
    assert first is not None
    assert second is None


def test_disallowed_attachment_rejected(tmp_path):
    adapter = EmailAdapter(upload_dir=tmp_path)
    raw = _make_email(
        attachment_name="evil.exe",
        attachment_data=b"MZ...",
        attachment_mime="application/x-msdownload",
    )
    message = adapter.receive_email(raw)
    assert message is not None
    assert message.attachments == []  # x-msdownload not on the whitelist


class _CaptureHandler:
    def __init__(self) -> None:
        self.envelopes = []

    async def handle_DATA(self, server, session, envelope):  # noqa: N802
        self.envelopes.append(envelope)
        return "250 OK"


def test_smtp_send_via_aiosmtpd():
    handler = _CaptureHandler()
    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        adapter = EmailAdapter(
            smtp_host="127.0.0.1", smtp_port=port, from_addr="consultant@example.com"
        )
        message = Message(id="m1", client_id="c_0001", channel=Channel.EMAIL, body="hello there")

        receipt = adapter.send(message, to_addr="client@example.com")

        assert receipt.ok
        assert receipt.external_id == "m1"
        assert len(handler.envelopes) == 1
        envelope = handler.envelopes[0]
        assert envelope.rcpt_tos == ["client@example.com"]
        content = getattr(envelope, "original_content", envelope.content)
        assert b"hello there" in content
    finally:
        controller.stop()
