"""Email channel demo / loop runner.

Loads .env (EMAIL_*), constructs the EmailAdapter, and exercises the channel:

    uv run python scripts/email_demo.py --receive            # poll inbox once
    uv run python scripts/email_demo.py --send to@x.com --body "hi"   # send
    uv run python scripts/email_demo.py --loop --ack         # poll every 30s, auto-ack

Requires EMAIL_IMAP_PASSWORD (a Gmail App Password) in .env for receive/send.
"""
from __future__ import annotations

import argparse
import time

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.config import load_env
from uk_visa_consultant.models import Channel, Message

_ACK = "Received — we've logged your message and will reply shortly."


def _receive_loop(adapter: EmailAdapter, loop: bool, ack: bool) -> None:
    while True:
        msgs = adapter.receive()
        for m in msgs:
            print(f"[{m.ts:%H:%M:%S}] {m.id} from={m.client_id} "
                  f"body={m.body[:60]!r} attachments={len(m.attachments)}")
            if ack:
                to = adapter.identity.email_for_client(m.client_id)
                reply = Message(id=f"{m.id}_ack", client_id=m.client_id,
                                channel=Channel.EMAIL, body=_ACK)
                print("  ack ->", adapter.send(reply, to_addr=to))
        if not loop:
            return
        time.sleep(30)


def main() -> None:
    load_env()
    adapter = EmailAdapter()

    ap = argparse.ArgumentParser()
    ap.add_argument("--receive", action="store_true", help="poll inbox once")
    ap.add_argument("--send", metavar="TO", help="send a message to this address")
    ap.add_argument("--body", default="Test message from uk-visa-consultant.")
    ap.add_argument("--loop", action="store_true", help="poll every 30s")
    ap.add_argument("--ack", action="store_true", help="auto-reply to new messages")
    args = ap.parse_args()

    if args.send:
        msg = Message(id="demo_1", client_id="c_demo", channel=Channel.EMAIL, body=args.body)
        print("send ->", adapter.send(msg, to_addr=args.send))
    if args.receive or args.loop:
        _receive_loop(adapter, loop=args.loop, ack=args.ack)
    if not (args.send or args.receive or args.loop):
        ap.print_help()


if __name__ == "__main__":
    main()
