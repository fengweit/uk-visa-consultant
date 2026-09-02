"""EmailAdapter — IMAP (inbound) + SMTP (outbound) over a canonical Message.

MIME parsing and identity mapping are pure, so they are testable with no
network. SMTP sending is exercised in tests against a local aiosmtpd server;
IMAP polling is wired but only runs against a real inbox.

Config comes from ``EMAIL_*`` env vars, each overridable at construction:
    EMAIL_IMAP_HOST / EMAIL_IMAP_PORT / EMAIL_IMAP_USER / EMAIL_IMAP_PASSWORD
    EMAIL_SMTP_HOST / EMAIL_SMTP_PORT / EMAIL_FROM
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Iterable

from uk_visa_consultant.channels.base import ChannelAdapter
from uk_visa_consultant.channels.identity import IdentityResolver
from uk_visa_consultant.models import Attachment, Channel, Message, SendReceipt

# Attachment hygiene (docs/specs/comms-layer.md): a whitelist rejects
# unexpected payloads. Kinds are the canonical three: pdf | image | text.
_ALLOWED_MIME = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "text/plain": "text",
    "text/csv": "text",
    "text/html": "text",
}
_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB


def _kind_for_mime(mime: str) -> str | None:
    return _ALLOWED_MIME.get(mime)


def _derive_message_id(seed: str) -> str:
    return "msg_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


@dataclass
class ParsedEmail:
    """Pure result of MIME parsing — no identity, no filesystem, no dedup."""

    message_id: str
    from_addr: str
    ts: datetime
    body: str = ""
    attachments: list[tuple[str, str, bytes]] = field(default_factory=list)  # (name, mime, payload)
    subject: str = ""
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)
    automated: bool = False


def _is_automated_message(msg: EmailMessage, from_addr: str) -> bool:
    local_part = from_addr.partition("@")[0].lower()
    if local_part.startswith(("no-reply", "noreply", "do-not-reply", "donotreply")):
        return True
    auto_submitted = str(msg.get("Auto-Submitted") or "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return True
    suppress = str(msg.get("X-Auto-Response-Suppress") or "").strip().lower()
    if suppress and suppress != "none":
        return True
    precedence = str(msg.get("Precedence") or "").strip().lower()
    return precedence in {"bulk", "list", "junk"}


def parse_email(raw: bytes) -> ParsedEmail:
    """Parse RFC5322 bytes into body text + attachments. Pure and deterministic."""
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    raw_id = msg.get("Message-ID") or msg.get("Message-Id") or ""
    message_id = raw_id.strip() or "fallback_" + hashlib.sha1(raw).hexdigest()

    from_addr = ""
    from_hdr = msg.get("From")
    if from_hdr:
        from_addr = parseaddr(str(from_hdr))[1]

    subject = str(msg.get("Subject") or "")
    in_reply_to = str(msg.get("In-Reply-To") or "").strip()
    references = [r.strip() for r in str(msg.get("References") or "").split() if r.strip()]
    automated = _is_automated_message(msg, from_addr)

    ts = datetime.now(timezone.utc)
    date_hdr = msg.get("Date")
    if date_hdr:
        try:
            ts = parsedate_to_datetime(str(date_hdr))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass

    body = _extract_body(msg)

    attachments: list[tuple[str, str, bytes]] = []
    for part in msg.iter_attachments():
        filename = part.get_filename()
        mime = part.get_content_type()
        raw_payload = part.get_payload(decode=True)
        payload = raw_payload if isinstance(raw_payload, bytes) else b""
        if filename and payload:
            attachments.append((filename, mime, payload))

    return ParsedEmail(
        message_id=message_id,
        from_addr=from_addr,
        ts=ts,
        body=body,
        attachments=attachments,
        subject=subject,
        in_reply_to=in_reply_to,
        references=references,
        automated=automated,
    )


def _extract_body(msg: EmailMessage) -> str:
    """Prefer text/plain; fall back to text/html; else ''."""
    text = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and not text:
                text = _decode_part(part)
            elif ctype == "text/html" and not html:
                html = _decode_part(part)
    else:
        if msg.get_content_type() == "text/plain":
            text = _decode_part(msg)
        elif msg.get_content_type() == "text/html":
            html = _decode_part(msg)
    return _strip_quoted_history((text or html or "").strip())


_QUOTED_REPLY_MARKERS = (
    re.compile(r"^On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^-+\s*Original Message\s*-+$", re.IGNORECASE),
    re.compile(r"^From:\s+.+$", re.IGNORECASE),
)


def _strip_quoted_history(body: str) -> str:
    """Keep only the newly authored part of a standard email reply."""
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or any(p.match(stripped) for p in _QUOTED_REPLY_MARKERS):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def _decode_part(part: EmailMessage) -> str:
    try:
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            text = part.get_payload()
            return text if isinstance(text, str) else ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError, ValueError):
        return ""


class EmailAdapter(ChannelAdapter):
    channel = Channel.EMAIL

    def __init__(
        self,
        identity: IdentityResolver | None = None,
        *,
        imap_host: str | None = None,
        imap_port: int | None = None,
        imap_user: str | None = None,
        imap_password: str | None = None,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        from_addr: str | None = None,
        upload_dir: str | Path = "data/uploads",
        seen_path: str | Path = "data/state/email_seen.json",
    ) -> None:
        self.identity = identity or IdentityResolver()
        self.imap_host = imap_host or os.environ.get("EMAIL_IMAP_HOST", "localhost")
        self.imap_port = imap_port or int(os.environ.get("EMAIL_IMAP_PORT", "993"))
        self.imap_user = imap_user or os.environ.get("EMAIL_IMAP_USER", "")
        self.imap_password = imap_password or os.environ.get("EMAIL_IMAP_PASSWORD", "")
        self.smtp_host = smtp_host or os.environ.get("EMAIL_SMTP_HOST", "localhost")
        self.smtp_port = smtp_port or int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        self.from_addr = from_addr or os.environ.get("EMAIL_FROM", "consultant@localhost")
        self.upload_dir = Path(upload_dir)
        self.seen_path = Path(seen_path)
        self._seen: set[str] = set(self._load_seen())
        self._last_subject: dict[str, str] = {}  # thread_root -> inbound subject

    def _load_seen(self) -> set[str]:
        """Persisted set of already-processed message ids (survives restarts)."""
        if self.seen_path.exists():
            try:
                return set(json.loads(self.seen_path.read_text()))
            except (json.JSONDecodeError, OSError):
                return set()
        return set()

    def _persist_seen(self) -> None:
        self.seen_path.parent.mkdir(parents=True, exist_ok=True)
        self.seen_path.write_text(json.dumps(sorted(self._seen)))

    # -- inbound: pure mapping ---------------------------------------------
    def receive_email(self, raw: bytes) -> Message | None:
        """Parse one raw email and map it to a Message (dedup + identity + disk).

        Returns ``None`` for a duplicate delivery.
        """
        parsed = parse_email(raw)
        if parsed.message_id in self._seen:
            return None
        self._seen.add(parsed.message_id)
        if parsed.automated:
            return None  # never converse with notification bots/autoresponders
        if parsed.from_addr and self.from_addr and parsed.from_addr.lower() == self.from_addr.lower():
            return None  # skip our own outbound mail (avoids self-reply loops)

        client_id = self.identity.resolve_email(parsed.from_addr)
        msg_id = _derive_message_id(parsed.message_id)
        thread_root = parsed.references[0] if parsed.references else (parsed.in_reply_to or parsed.message_id)
        self._last_subject[thread_root] = parsed.subject

        attachments: list[Attachment] = []
        for filename, mime, payload in parsed.attachments:
            stored = self._store_attachment(client_id, msg_id, filename, mime, payload)
            if stored is not None:
                attachments.append(stored)

        return Message(
            id=msg_id,
            client_id=client_id,
            channel=Channel.EMAIL,
            ts=parsed.ts,
            body=parsed.body,
            attachments=attachments,
            thread_id=parsed.message_id,
            thread_root=thread_root,
            references=parsed.references,
        )

    def _store_attachment(
        self, client_id: str, msg_id: str, filename: str, mime: str, payload: bytes
    ) -> Attachment | None:
        kind = _kind_for_mime(mime)
        if kind is None:
            return None  # whitelist rejects the payload
        if len(payload) > _MAX_ATTACHMENT_BYTES:
            return None  # size whitelist rejects the payload
        safe = _sanitize_filename(filename)
        directory = self.upload_dir / client_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{msg_id}_{safe}"
        path.write_bytes(payload)
        return Attachment(kind=kind, local_path=str(path), mime=mime)

    # -- inbound: IMAP polling ---------------------------------------------
    def receive(self) -> list[Message]:
        """Poll IMAP for unseen mail, map to Message, mark seen (cross-restart dedup).

        Mark-as-seen is the standard IMAP dedup; the in-memory + persisted
        ``_seen`` set is a second layer so a re-poll never re-processes a
        message id that was already handled.
        """
        import imaplib

        messages: list[Message] = []
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as conn:
            conn.login(self.imap_user, self.imap_password)
            conn.select("INBOX")
            _, data = conn.search(None, "UNSEEN")
            for num in data[0].split():
                _, msg_data = conn.fetch(num, "(RFC822)")
                raw = _coerce_raw(msg_data)
                if raw is None:
                    continue
                message = self.receive_email(raw)
                conn.store(num, "+FLAGS", "\\Seen")
                if message is not None:
                    messages.append(message)
        self._persist_seen()
        return messages

    # -- outbound ----------------------------------------------------------
    def send(self, message: Message, *, to_addr: str | None = None) -> SendReceipt:
        to = to_addr or self.identity.email_for_client(message.client_id)
        if not to:
            return SendReceipt(ok=False, error=f"no recipient email for client {message.client_id}")
        try:
            subject_key = message.thread_root or message.thread_id or message.client_id
            orig_subject = self._last_subject.get(subject_key)
            subject = _reply_subject(orig_subject) if orig_subject is not None else "UK visa update"
            outbound_id = self._smtp_send(
                to=to,
                subject=subject,
                body=message.body,
                attachments=[
                    (a.local_path, a.mime) for a in message.attachments
                ],
                thread_id=message.thread_id,
                references=message.references,
            )
            return SendReceipt(ok=True, external_id=outbound_id or message.id)
        except Exception as exc:  # noqa: BLE001 — transport boundary, fail closed
            return SendReceipt(ok=False, error=str(exc))

    def send_media(self, local_path: str, mime: str, recipient: str | None = None) -> SendReceipt:
        if not recipient:
            return SendReceipt(ok=False, error="send_media requires a recipient email address")
        try:
            self._smtp_send(
                to=recipient,
                subject="UK visa document",
                body="",
                attachments=[(local_path, mime)],
            )
            return SendReceipt(ok=True, external_id=None)
        except Exception as exc:  # noqa: BLE001
            return SendReceipt(ok=False, error=str(exc))

    def _smtp_send(
        self, to: str, subject: str, body: str, attachments: Iterable[tuple[str, str]],
        thread_id: str | None = None, references: list[str] | None = None,
    ) -> str | None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        if thread_id:
            msg["In-Reply-To"] = thread_id
            chain = list(references or [])
            if thread_id not in chain:
                chain.append(thread_id)
            msg["References"] = " ".join(chain)
            msg["Message-ID"] = f"<agent-{thread_id.strip('<>')}@ukvisa>"
        msg.set_content(body or "(no message body)")
        for path, mime in attachments:
            data = Path(path).read_bytes()
            maintype, subtype = (mime.split("/", 1) + ["octet-stream"])[:2]
            msg.add_attachment(
                data, maintype=maintype, subtype=subtype, filename=Path(path).name
            )

        smtp = (
            smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            if self.smtp_port == 465
            else smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
        )
        with smtp:
            if self.smtp_port != 465 and self.imap_user:
                smtp.starttls()
            if self.imap_user:
                smtp.login(self.imap_user, self.imap_password)
            smtp.send_message(msg)
        return str(msg.get("Message-ID")) if msg.get("Message-ID") else None


def _reply_subject(subject: str) -> str:
    """Keep replies in the source thread without accumulating Re: prefixes."""
    base = subject.strip()
    while base.lower().startswith("re:"):
        base = base[3:].strip()
    return f"Re: {base}" if base else "Re:"


def _sanitize_filename(filename: str) -> str:
    keep = []
    for ch in filename:
        if ch.isalnum() or ch in "._-":
            keep.append(ch)
        else:
            keep.append("_")
    clean = "".join(keep).strip("._")
    return clean or "attachment"


def _coerce_raw(msg_data: object) -> bytes | None:
    """Extract RFC822 bytes from an imaplib fetch result (shapes vary by server)."""
    if isinstance(msg_data, bytes):
        return msg_data
    if isinstance(msg_data, (tuple, list)):
        for item in msg_data:
            if isinstance(item, bytes):
                # A single response may be `(header_bytes, body_bytes)`; take the
                # one that actually looks like a message (has an RFC822 header).
                if b"\r\n" in item and b":" in item:
                    return item
            elif isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
    return None
