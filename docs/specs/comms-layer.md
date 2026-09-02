# Spec — Comms layer (information & communication layer)

## Purpose

The transport boundary between the agent and the client. It normalizes every inbound channel (WhatsApp, email, local test harness) into a canonical `Message` and routes outbound messages back through the originating channel. It contains **zero business logic** — it is transport only, so it can be built and tested as a separate network layer, exactly as specified.

## Position in pipeline

```
channel event ──► ChannelAdapter.receive() ──► Message ──► (core pipeline)
(core pipeline) ──► Message ──► ChannelAdapter.send() ──► channel
```

## Canonical types

```jsonc
// Message
{
  "id": "msg_8f3a...",              // stable id, idempotent on the channel side
  "client_id": "c_0021",            // resolved across channels (see identity)
  "channel": "whatsapp | email | local",
  "ts": "2026-09-01T14:02:11Z",
  "body": "text of the message",
  "attachments": [                   // normalized media references
    { "kind": "pdf|image|text", "local_path": "/data/uploads/a.pdf", "mime": "application/pdf" }
  ]
}
```

```jsonc
// ChannelAdapter interface (conceptual)
{
  "receive": "() -> Message[]",      // pull new inbound messages
  "send":    "(Message) -> SendReceipt",   // SendReceipt: {ok, external_id, error?}
  "send_media": "(path, mime) -> SendReceipt"
}
```

## Implementations (build order)

### 1. `LocalAdapter` — first, for loop testing

- Reads messages from a queue/script (in-process list or a JSONL file), returns them as `Message` with `channel="local"`.
- `send` appends to an outbound list or prints — the test harness asserts on it.
- `send_media` records the path; no actual network.
- **Purpose:** drive the entire core loop end-to-end with zero infrastructure, so intent/parse/gap/assemble/verify are exercised long before any channel integration.

### 2. `WhatsAppAdapter` — Meta WhatsApp Cloud API

- **Inbound:** Meta Cloud API webhook → `POST /webhooks/whatsapp`. Verify the `X-Hub-Signature-256` using the app secret; reject otherwise. Extract `messages` events (text + media), download media by media id, map to `Message`.
- **Outbound:** send text via `/messages`; send media via media upload then `/messages` with media object.
- **Templates:** the first outbound message to a client in a 24h window must be an approved message template; free-form messages only within a customer-service window. The adapter enforces template-vs-freeform selection and raises on violations.
- **Identity:** map `wa_id` → `client_id`.

### 3. `EmailAdapter` — IMAP (inbound) + SMTP (outbound)

- **Inbound:** poll IMAP (IDLE optional), parse MIME; text → `body`, attachments → `attachments[]`.
- **Outbound:** SMTP send; `send_media` = attachment.
- **Identity:** map `From` address → `client_id`.

## Client identity resolution

A client may appear on both channels. The layer resolves both to one `client_id`:

- Primary key candidates: `phone` (WhatsApp) and `email` (Email).
- A `Client.contact` map links them. On first contact, a `client_id` is minted; later contacts on the other channel are matched by an explicit "link" (e.g. the client says "I also emailed you", or an OTP-style confirmation).
- **No silent merging** — a phone and email are linked only on explicit confirmation, never on name similarity alone. Unlinked → separate `client_id` until confirmed.

## Stability measures

- **Idempotency:** every inbound event carries an external id; duplicate delivery (webhook retries, IMAP re-read) is deduped by that id. `Message.id` is derived from it.
- **Signature verification fail-closed:** an unverifiable WhatsApp webhook is dropped and logged, never processed.
- **No partial sends:** outbound failure returns a `SendReceipt{ok:false, error}` and the case records the unsent state; a retry path re-sends, it does not silently drop.
- **Attachment hygiene:** downloaded media lands under `data/uploads/` (gitignored) keyed by client + message id; a size/type whitelist rejects unexpected payloads.

## Example

```
LocalAdapter.receive() →
  Message{ channel:"local", client_id:"c_0021", body:"here is my passport",
           attachments:[{kind:"image", local_path:"/data/uploads/c_0021/passport.jpg"}] }
```

## Test plan

1. `LocalAdapter` round-trips `receive → send` and the harness observes the outbound queue.
2. WhatsApp webhook: valid signature → processed; tampered signature → dropped (assert no `Message` emitted).
3. WhatsApp template rule: free-form text as first contact raises; template message succeeds.
4. Email: MIME with text + PDF attachment → `Message` with body + one `attachments[]` entry.
5. Identity: phone `A` and email `B` → two `client_id`s; after explicit link → one.
6. Duplicate webhook delivery → exactly one `Message`.

## Open questions

- WhatsApp Business Account / phone number / template approval: required before live; not blocking local-loop development.
- Email: dedicated inbox per client or a shared inbox with routing tags? (Recommend shared + routing tag for MVP.)
