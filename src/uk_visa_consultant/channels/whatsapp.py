"""WhatsAppAdapter — Meta WhatsApp Cloud API over a canonical Message.

Inbound is push-based (webhook), not pull: the Meta Cloud API POSTs JSON to
``/webhooks/whatsapp``. ``handle_webhook`` verifies the ``X-Hub-Signature-256``
(fail-closed), extracts message events, dedupes by external id, and maps each to
a ``Message``. No web framework is required — every entry point is a pure
function or a plain method call.

Signature verification is HMAC-SHA256 over the **raw body bytes** with the app
secret (``WHATSAPP_APP_SECRET``), compared in constant time to the
``X-Hub-Signature-256`` header's ``sha256=<hex>`` value.

Template rule (docs/specs/comms-layer.md): the first outbound message to a
client in a 24h window must be an approved template; free-form text is only
allowed inside a customer-service window opened by a recent inbound message.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from uk_visa_consultant.channels.base import ChannelAdapter, ChannelError
from uk_visa_consultant.channels.identity import IdentityResolver
from uk_visa_consultant.models import Attachment, Channel, Message, SendReceipt

_CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)


class SignatureVerificationError(ChannelError):
    """Raised/returned when a webhook signature cannot be verified."""


class TemplateWindowError(ChannelError):
    """Raised when a free-form outbound message violates the 24h template rule."""


def verify_signature(payload: bytes, headers: Mapping[str, str], app_secret: str) -> bool:
    """Pure signature check: HMAC-SHA256(raw body) == X-Hub-Signature-256.

    ``headers`` keys may arrive in any casing; the header is matched
    case-insensitively. Returns ``False`` (fail-closed) when absent, malformed,
    or mismatched.
    """
    if not app_secret:
        return False
    signature = None
    for key, value in headers.items():
        if str(key).lower() == "x-hub-signature-256":
            signature = value
            break
    if not signature or not signature.startswith("sha256="):
        return False
    expected = signature[len("sha256="):]
    computed = hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, expected)


def _derive_message_id(external_id: str) -> str:
    return "msg_" + hashlib.sha1(external_id.encode("utf-8")).hexdigest()[:16]


def _extract_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull every ``messages[]`` event out of a Cloud API webhook payload."""
    events: list[dict[str, Any]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            messages = value.get("messages", []) or []
            for msg in messages:
                if isinstance(msg, dict):
                    events.append(msg)
    return events


class WhatsAppAdapter(ChannelAdapter):
    channel = Channel.WHATSAPP

    def __init__(
        self,
        app_secret: str | None = None,
        identity: IdentityResolver | None = None,
        *,
        upload_dir: str | Path = "data/uploads",
        http_client: Any | None = None,
    ) -> None:
        self.app_secret = app_secret if app_secret is not None else os.environ.get(
            "WHATSAPP_APP_SECRET", ""
        )
        self.identity = identity or IdentityResolver()
        self.upload_dir = Path(upload_dir)
        self._http = http_client  # httpx.Client, injectable for tests
        self._seen: set[str] = set()
        self._last_inbound: dict[str, datetime] = {}  # client_id -> last inbound ts
        self._outbox: list[tuple[Message, str | None]] = []

    # -- inbound -----------------------------------------------------------
    def handle_webhook(self, payload: bytes, headers: Mapping[str, str]) -> list[Message]:
        """Verify signature, then map new message events to Message.

        Tampered/unverifiable payloads are dropped (fail-closed) — returns ``[]``
        and never emits a Message. Duplicate deliveries are deduped by external
        id; the second delivery contributes nothing.
        """
        if not verify_signature(payload, headers, self.app_secret):
            return []
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []

        new_messages: list[Message] = []
        for event in _extract_messages(data):
            message = self._event_to_message(event)
            if message is None:
                continue
            if message.id in self._seen:
                continue
            self._seen.add(message.id)
            new_messages.append(message)
        return new_messages

    def _event_to_message(self, event: dict[str, Any]) -> Message | None:
        wa_id = event.get("from")
        external_id = event.get("id")
        if not wa_id or not external_id:
            return None

        client_id = self.identity.resolve_phone(str(wa_id))
        self._last_inbound[client_id] = datetime.now(timezone.utc)

        msg_id = _derive_message_id(str(external_id))
        try:
            ts = datetime.fromtimestamp(float(event.get("timestamp", 0)), tz=timezone.utc)
        except (TypeError, ValueError):
            ts = datetime.now(timezone.utc)

        etype = event.get("type")
        body = ""
        attachments: list[Attachment] = []

        if etype == "text":
            body = (event.get("text") or {}).get("body", "")
        else:
            # media types: image | document | audio | sticker | video
            media = event.get(etype) if isinstance(etype, str) else None
            if isinstance(media, dict):
                media_id = media.get("id")
                mime = media.get("mime_type") or "application/octet-stream"
                caption = media.get("caption") or ""
                body = caption
                if media_id:
                    attachment = self._download_media(str(media_id), client_id, msg_id, mime)
                    if attachment is not None:
                        attachments.append(attachment)

        return Message(
            id=msg_id,
            client_id=client_id,
            channel=Channel.WHATSAPP,
            ts=ts,
            body=body,
            attachments=attachments,
        )

    def _download_media(
        self, media_id: str, client_id: str, msg_id: str, mime: str
    ) -> Attachment | None:
        """Download media by id and store under data/uploads/<client>/.

        Uses the injected httpx client when available (real integration);
        otherwise stubs out and returns ``None`` — deterministic, no network.
        """
        if self._http is None:
            return None
        # Real path: GET /{media_id} then save. Kept stub-safe for tests.
        self.upload_dir.joinpath(client_id).mkdir(parents=True, exist_ok=True)
        ext = _ext_for_mime(mime)
        path = self.upload_dir / client_id / f"{msg_id}{ext}"
        try:
            resp = self._http.get(f"https://graph.facebook.com/v19.0/{media_id}")
            resp.raise_for_status()
            path.write_bytes(resp.content)
        except Exception:  # noqa: BLE001 — transport boundary, fail closed
            return None
        return Attachment(kind=_kind_for_mime(mime), local_path=str(path), mime=mime)

    def receive(self) -> list[Message]:
        """WhatsApp inbound is push-based (webhook); there is no pull queue."""
        return []

    # -- outbound ----------------------------------------------------------
    def in_customer_service_window(self, client_id: str, now: datetime | None = None) -> bool:
        last = self._last_inbound.get(client_id)
        if last is None:
            return False
        return ((now or datetime.now(timezone.utc)) - last) < _CUSTOMER_SERVICE_WINDOW

    def send(self, message: Message, *, template: str | None = None) -> SendReceipt:
        """Enforce the template-vs-freeform rule, then record the outbound send.

        ``template`` is an approved template name (e.g. ``"appointment_reminder"``).
        When omitted, the message is free-form and is only allowed inside an
        active customer-service window; otherwise ``TemplateWindowError``.
        """
        if template is None and not self.in_customer_service_window(message.client_id):
            raise TemplateWindowError(
                f"no active 24h customer-service window for {message.client_id}; "
                "the first outbound message must use an approved template"
            )
        self._outbox.append((message, template))
        return SendReceipt(ok=True, external_id=message.id)

    def send_media(self, local_path: str, mime: str, recipient: str | None = None) -> SendReceipt:
        # Media outbound is recorded; real integration uploads + sends via the
        # Cloud API. Recipient = wa_id.
        self._outbox.append(
            (
                Message(
                    id="media_" + Path(local_path).stem,
                    client_id=recipient or "unknown",
                    channel=Channel.WHATSAPP,
                    body="",
                    attachments=[Attachment(kind=_kind_for_mime(mime), local_path=local_path, mime=mime)],
                ),
                None,
            )
        )
        return SendReceipt(ok=True, external_id=None)

    @property
    def outbox(self) -> list[tuple[Message, str | None]]:
        return list(self._outbox)


def _kind_for_mime(mime: str) -> str:
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("text/"):
        return "text"
    return "text"


def _ext_for_mime(mime: str) -> str:
    return {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "text/plain": ".txt",
    }.get(mime, ".bin")
