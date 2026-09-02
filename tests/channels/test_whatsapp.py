"""WhatsApp webhook tests: signature verification, template rule, dedup."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from uk_visa_consultant.channels.whatsapp import (
    TemplateWindowError,
    WhatsAppAdapter,
    verify_signature,
)
from uk_visa_consultant.models import Channel, Message

SECRET = "shhh_app_secret"


def _payload(body="hi") -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "111",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "999"},
                                "contacts": [{"wa_id": "447700900123"}],
                                "messages": [
                                    {
                                        "from": "447700900123",
                                        "id": "wamid.ABC123",
                                        "timestamp": "1690000000",
                                        "type": "text",
                                        "text": {"body": body},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")


def _signed(payload: bytes, secret: str = SECRET) -> dict[str, str]:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={sig}"}


def test_verify_signature_pure_function():
    payload = _payload()
    headers = _signed(payload)
    assert verify_signature(payload, headers, SECRET) is True

    # case-insensitive header matching
    assert verify_signature(payload, {"x-hub-signature-256": headers["X-Hub-Signature-256"]}, SECRET) is True

    # tampered body / wrong secret / missing header all fail closed
    assert verify_signature(payload.replace(b"hi", b"yo"), headers, SECRET) is False
    assert verify_signature(payload, headers, "wrong_secret") is False
    assert verify_signature(payload, {}, SECRET) is False
    assert verify_signature(payload, {"X-Hub-Signature-256": "not-a-hex"}, SECRET) is False


def test_valid_webhook_emits_message():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    payload = _payload("here is my passport")
    messages = adapter.handle_webhook(payload, _signed(payload))

    assert len(messages) == 1
    m = messages[0]
    assert m.channel is Channel.WHATSAPP
    assert m.body == "here is my passport"
    assert m.client_id  # resolved from wa_id
    assert m.id == "msg_" + hashlib.sha1(b"wamid.ABC123").hexdigest()[:16]


def test_tampered_webhook_is_dropped():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    payload = _payload()

    # tampered signature
    bad = {"X-Hub-Signature-256": "sha256=" + "0" * 64}
    assert adapter.handle_webhook(payload, bad) == []

    # tampered body with otherwise-valid signature
    assert adapter.handle_webhook(payload.replace(b"hi", b"yo"), _signed(payload)) == []

    # missing signature
    assert adapter.handle_webhook(payload, {}) == []


def test_duplicate_webhook_delivery_deduped():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    payload = _payload()
    headers = _signed(payload)

    first = adapter.handle_webhook(payload, headers)
    second = adapter.handle_webhook(payload, headers)

    assert len(first) == 1
    assert second == []


def test_template_rule_freeform_first_contact_raises():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    msg = Message(id="m1", client_id="c_0001", channel=Channel.WHATSAPP, body="hello")

    with pytest.raises(TemplateWindowError):
        adapter.send(msg)  # free-form with no customer-service window


def test_template_rule_template_succeeds():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    msg = Message(id="m1", client_id="c_0001", channel=Channel.WHATSAPP, body="hello")

    receipt = adapter.send(msg, template="appointment_reminder")
    assert receipt.ok
    assert adapter.outbox[0] == (msg, "appointment_reminder")


def test_freeform_allowed_inside_customer_service_window():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    payload = _payload("hi")
    inbound = adapter.handle_webhook(payload, _signed(payload))
    client_id = inbound[0].client_id

    # an inbound message opens the window; free-form outbound now allowed
    reply = Message(id="m2", client_id=client_id, channel=Channel.WHATSAPP, body="sure")
    receipt = adapter.send(reply)
    assert receipt.ok


def test_window_expires_after_24h():
    adapter = WhatsAppAdapter(app_secret=SECRET)
    now = datetime.now(timezone.utc)
    adapter._last_inbound["c_0001"] = now
    assert adapter.in_customer_service_window("c_0001", now=now) is True
    assert adapter.in_customer_service_window("c_0001", now=now + timedelta(hours=25)) is False
