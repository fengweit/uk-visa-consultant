"""Gateway loop + WhatsApp webhook (signed fixtures, no live Meta/email)."""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from uk_visa_consultant.channels.whatsapp import WhatsAppAdapter
from uk_visa_consultant.gateway.loop import Gateway
from uk_visa_consultant.gateway.server import create_app
from uk_visa_consultant.models import Channel, Message


def _signed(body: bytes, secret: str) -> dict:
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}


def test_gateway_reply_on_same_channel():
    gw = Gateway()
    msg = Message(id="m1", client_id="c1", channel=Channel.LOCAL, body="what documents do I need?")
    reply = gw.handle(msg)
    assert reply.channel == Channel.LOCAL
    assert reply.client_id == "c1"
    assert "passport" in reply.body


def test_gateway_escalation_reply():
    gw = Gateway()
    reply = gw.handle(Message(id="m2", client_id="c1", channel=Channel.LOCAL, body="I want a human"))
    assert "specialist" in reply.body


def test_whatsapp_webhook_valid_signature_replies():
    wa = WhatsAppAdapter(app_secret="secret")
    client = TestClient(create_app(wa=wa))
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [
        {"id": "w1", "from": "15551234567", "type": "text",
         "text": {"body": "here is my passport"}, "timestamp": "1750000000"},
    ]}}]}]}).encode()
    r = client.post("/webhooks/whatsapp", content=body, headers=_signed(body, "secret"))
    assert r.status_code == 200
    assert wa.outbox  # a free-form reply was queued (inbound opened the 24h window)


def test_whatsapp_webhook_tampered_signature_rejected():
    wa = WhatsAppAdapter(app_secret="secret")
    client = TestClient(create_app(wa=wa))
    body = json.dumps({"entry": []}).encode()
    r = client.post("/webhooks/whatsapp", content=body, headers=_signed(body, "wrong"))
    assert r.status_code == 200
    assert not wa.outbox  # fail-closed: nothing processed, nothing queued


def test_whatsapp_webhook_verify_handshake():
    client = TestClient(create_app(wa=WhatsAppAdapter(app_secret="s")))
    r = client.get("/webhooks/whatsapp",
                   params={"hub.mode": "subscribe", "hub.verify_token": "unset", "hub.challenge": "ch123"})
    assert r.status_code == 403  # no VERIFY_TOKEN configured -> reject


def test_healthz():
    assert TestClient(create_app(wa=WhatsAppAdapter(app_secret="s"))).get("/healthz").json() == {"status": "ok"}
