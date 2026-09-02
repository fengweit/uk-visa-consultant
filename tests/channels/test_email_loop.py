"""Email polling loop: mark-seen + persisted-seen dedup (no network)."""
from __future__ import annotations

import imaplib
import json
from email.message import EmailMessage

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.models import Channel, Message


def _raw_email(from_addr="alice@example.com", body="hello there", msg_id="<m1@example>"):
    m = EmailMessage()
    m["From"] = from_addr
    m["To"] = "visa@example.com"
    m["Subject"] = "test"
    m["Message-ID"] = msg_id
    m["Date"] = "Tue, 1 Sep 2026 12:00:00 +0000"
    m.set_content(body)
    return m.as_bytes()


class _FakeIMAP:
    def __init__(self, raws):
        self._raws = raws
        self.stored = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        return ("OK", None)

    def select(self, mailbox):
        return ("OK", [b"1"])

    def search(self, *criteria):
        nums = " ".join(str(i + 1) for i in range(len(self._raws)))
        return ("OK", [nums.encode()])

    def fetch(self, num, parts):
        idx = int(num) - 1
        raw = self._raws[idx]
        return ("OK", [(f"1 (RFC822 {len(raw)}".encode(), raw), b")"])

    def store(self, num, flags, value):
        self.stored.append((num, flags, value))
        return ("OK", None)


def test_receive_marks_seen_and_returns_message(monkeypatch, tmp_path):
    fake = _FakeIMAP([_raw_email()])
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port: fake)

    adapter = EmailAdapter(
        imap_host="imap.example", imap_user="u", imap_password="p",
        seen_path=tmp_path / "seen.json",
    )
    msgs = adapter.receive()

    assert len(msgs) == 1
    assert msgs[0].body == "hello there"
    assert msgs[0].client_id  # identity resolver mints a client id
    assert fake.stored == [(b"1", "+FLAGS", "\\Seen")]


def test_receive_skips_persisted_seen(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps(["<m1@example>"]))  # pre-seeded raw Message-ID

    fake = _FakeIMAP([_raw_email()])
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port: fake)

    adapter = EmailAdapter(
        imap_host="imap.example", imap_user="u", imap_password="p",
        seen_path=seen_path,
    )
    assert adapter.receive() == []  # already-seen id -> skipped


def test_seen_persists_across_instances(monkeypatch, tmp_path):
    seen_path = tmp_path / "seen.json"
    fake = _FakeIMAP([_raw_email()])
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port: fake)

    first = EmailAdapter(imap_host="x", imap_user="u", imap_password="p", seen_path=seen_path)
    assert len(first.receive()) == 1

    # A fresh adapter instance (simulating restart) must skip the same message.
    fake2 = _FakeIMAP([_raw_email()])
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port: fake2)
    second = EmailAdapter(imap_host="x", imap_user="u", imap_password="p", seen_path=seen_path)
    assert second.receive() == []


def test_reply_threads_under_original_email(monkeypatch, tmp_path):
    adapter = EmailAdapter(imap_host="x", imap_user="u", imap_password="p",
                           seen_path=tmp_path / "seen.json")
    inbound = adapter.receive_email(_raw_email())
    assert inbound.thread_id == "<m1@example>"

    captured = {}

    def fake_smtp_send(self, to, subject, body, attachments, thread_id=None):
        captured["thread_id"] = thread_id
        captured["subject"] = subject

    monkeypatch.setattr(EmailAdapter, "_smtp_send", fake_smtp_send)
    reply = Message(id="r1", client_id=inbound.client_id, channel=Channel.EMAIL,
                    body="got it", thread_id=inbound.thread_id)
    adapter.send(reply)
    assert captured["thread_id"] == "<m1@example>"
    assert captured["subject"] == "Re: test"


def test_skips_own_outbound_mail(tmp_path):
    adapter = EmailAdapter(imap_host="x", imap_user="u", imap_password="p",
                           from_addr="fengwei.demo.uk.visa@gmail.com",
                           seen_path=tmp_path / "seen.json")
    raw = _raw_email(from_addr="fengwei.demo.uk.visa@gmail.com")
    assert adapter.receive_email(raw) is None
