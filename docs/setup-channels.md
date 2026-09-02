# Setting up the two channels

The gateway (`scripts/run_gateway.py`) runs one process with two inbound paths:

- **Email** — IMAP polling + SMTP send (no public URL needed).
- **WhatsApp** — Meta Cloud API webhook (requires a public HTTPS URL).

Both route through the same `Gateway` loop (`message → agent → reply`).

## Email (works with just a mailbox)

1. Create a dedicated inbox (Gmail/Workspace or custom domain).
2. **Enable IMAP** and create an **App Password** (Gmail: 2FA → Security → App passwords).
3. Fill `.env`:

```
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USER=fengwei.demo.uk.visa@gmail.com
EMAIL_IMAP_PASSWORD=<app password>
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_FROM=fengwei.demo.uk.visa@gmail.com
```

The poller starts automatically when `EMAIL_IMAP_PASSWORD` is set, and polls
every 30s (mark-as-seen + persisted dedup prevent re-processing).

## WhatsApp (needs Meta + a public URL)

1. **Meta Developer app** → add the WhatsApp product.
2. Get a **test number** (instant) or a real **WABA + phone number**.
3. Get a **permanent access token** and **Phone Number ID**; note the **App Secret** and a **Verify Token**.
4. Expose the webhook publicly: `cloudflared tunnel --url http://localhost:8000` (or ngrok).
5. Set the webhook callback URL to `https://<tunnel>/webhooks/whatsapp` with the verify token.
6. Fill `.env`:

```
WHATSAPP_ACCESS_TOKEN=<token>
WHATSAPP_PHONE_NUMBER_ID=<id>
WHATSAPP_APP_SECRET=<app secret>
WHATSAPP_VERIFY_TOKEN=<verify token>
```

Signature verification (HMAC-SHA256) is fail-closed; tampered webhooks are dropped.
The first outbound message in a 24h window must be an approved template — submit
templates for the reminder/follow-up messages before going live.

## Run

```
uv run python scripts/run_gateway.py          # serves WhatsApp webhook + email poll on :8000
```
