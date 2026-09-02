"""Run the gateway: FastAPI server (WhatsApp webhook + health) + email poll loop.

Usage:
    uv run python scripts/run_gateway.py

Loads .env. The email poller starts only if EMAIL_IMAP_PASSWORD is set; the
WhatsApp webhook needs a public URL (ngrok/cloudflared) plus WHATSAPP_* creds.
"""
from __future__ import annotations

import os
import threading
import time


def _email_loop():
    from uk_visa_consultant.channels.email import EmailAdapter
    from uk_visa_consultant.gateway.loop import Gateway

    gateway = Gateway()
    adapter = EmailAdapter()
    while True:
        try:
            for message in adapter.receive():
                reply = gateway.handle(message)
                adapter.send(reply, to_addr=adapter.identity.email_for_client(message.client_id))
        except Exception as exc:  # transport boundary — log and keep polling
            print(f"[email-loop] {exc}")
        time.sleep(30)


def main() -> None:
    from uk_visa_consultant.config import load_env
    load_env()

    if os.environ.get("EMAIL_IMAP_PASSWORD"):
        threading.Thread(target=_email_loop, daemon=True).start()
        print("[gateway] email poller started")

    import uvicorn
    from uk_visa_consultant.gateway.server import create_app
    port = int(os.environ.get("PORT", "8000"))
    print(f"[gateway] serving on :{port}")
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
