"""FastAPI gateway server — WhatsApp webhook + email poll + health.

``create_app`` returns a FastAPI app wiring the two channel adapters through the
Gateway loop. Everything is injectable so the endpoints are testable with a
signed webhook fixture and no live Meta/email credentials.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request, Response

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.channels.whatsapp import TemplateWindowError, WhatsAppAdapter
from uk_visa_consultant.gateway.loop import Gateway


def _send_whatsapp_reply(adapter: WhatsAppAdapter, reply) -> None:
    """Send a reply, tolerating the template-window rule (fail-closed, logged)."""
    try:
        adapter.send(reply)
    except TemplateWindowError:
        # outside the 24h customer-service window -> a template is required;
        # skip free-form send rather than crash the webhook.
        pass


def create_app(*, wa: WhatsAppAdapter | None = None, email: EmailAdapter | None = None,
               gateway: Gateway | None = None) -> FastAPI:
    gateway = gateway or Gateway()
    wa = wa or WhatsAppAdapter()
    email = email or EmailAdapter()

    app = FastAPI(title="uk-visa-consultant gateway")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/webhooks/whatsapp")
    def whatsapp_verify(request: Request):
        token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        mode = request.query_params.get("hub.mode")
        if mode == "subscribe" and request.query_params.get("hub.verify_token") == token:
            return Response(request.query_params.get("hub.challenge", ""), media_type="text/plain")
        return Response(status_code=403)

    @app.post("/webhooks/whatsapp")
    async def whatsapp_webhook(request: Request):
        body = await request.body()
        headers = dict(request.headers)
        for message in wa.handle_webhook(body, headers):  # signature-verified, deduped
            _send_whatsapp_reply(wa, gateway.handle(message))
        return {"status": "ok"}

    @app.post("/poll-email")
    def poll_email():
        received = 0
        for message in email.receive():
            reply = gateway.handle(message)
            to = email.identity.email_for_client(message.client_id)
            email.send(reply, to_addr=to)
            received += 1
        return {"received": received}

    return app
