"""Interactive local demo of the consultant loop (no credentials, no network).

    uv run python scripts/demo.py

Type messages as the applicant; the agent replies. Commands:
    attach <path>            attach a file (pdf/image) with your next message
    case <case_id>           submit a whole corpus case (e.g. student_001_complete)
    quit / q                 exit
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from uk_visa_consultant.gateway.loop import Gateway
from uk_visa_consultant.models import Attachment, Channel, Message


def _run_case(gateway: Gateway, corpus: Path, case_id: str) -> None:
    matches = list(corpus.glob(f"*/{case_id}/case.json")) if "/" not in case_id \
        else [corpus / case_id / "case.json"]
    cj = matches[0] if matches else None
    if not cj or not cj.exists():
        print(f"Agent: (no such case: {case_id})")
        return
    meta = json.loads(cj.read_text())
    client_id = f"c_{meta['case_id']}"
    route = Message(id=f"m_{time.time_ns()}", client_id=client_id, channel=Channel.LOCAL,
                    body=f"I want a {meta['visa_type']} visa")
    print(f"Agent: {gateway.handle(route).body}")
    for d in meta["documents"]:
        m = Message(id=f"m_{time.time_ns()}", client_id=client_id, channel=Channel.LOCAL,
                    body="here is my document",
                    attachments=[Attachment(kind="pdf", local_path=str(cj.parent / d["file"]),
                                            mime="application/pdf")])
        reply = gateway.handle(m)
        print(f"  [submitted {d['file']}] Agent: {reply.body}")


def main() -> None:
    gateway = Gateway()
    corpus = Path("data/corpus")
    print("=== uk-visa-consultant demo ===")
    print("Type a message as the applicant; the agent replies.")
    print("Commands:  attach <path>  |  case <case_id>  |  quit\n")

    pending: list[Attachment] = []
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            break
        if text.lower().startswith("case "):
            _run_case(gateway, corpus, text.split(maxsplit=1)[1])
            continue
        if text.lower().startswith("attach "):
            path = text.split(maxsplit=1)[1].strip()
            pending = [Attachment(kind="pdf", local_path=path, mime="application/pdf")]
            print(f"(attached {path} — send your message now)")
            continue

        msg = Message(id=f"m_{time.time_ns()}", client_id="c_demo", channel=Channel.LOCAL,
                      body=text, attachments=pending)
        pending = []
        print(f"Agent: {gateway.handle(msg).body}")


if __name__ == "__main__":
    main()
