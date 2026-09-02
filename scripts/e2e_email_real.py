"""Real email E2E over actual SMTP/IMAP — client → agent → client.

For a route's corpus cases, the test CLIENT account (EMAIL_CLIENT_*) sends emails
(with PDFs) to the AGENT account (EMAIL_*), a fresh Gateway processes them via the
agent's IMAP, replies via the agent's SMTP, and we verify the reply reaches the
client inbox — correctly threaded (In-Reply-To / Re:) and with the right gap.

Usage:
    uv run python scripts/e2e_email_real.py <route>   # visitor|student|worker|spouse|all
"""
from __future__ import annotations

import imaplib
import json
import os
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.config import load_env
from uk_visa_consultant.gateway.loop import Gateway

load_env()

AGENT = os.environ["EMAIL_IMAP_USER"]
CLIENT = os.environ["EMAIL_CLIENT_USER"]
CLIENT_PASS = os.environ["EMAIL_CLIENT_PASSWORD"]

DOC_BODY = {
    "passport": "here is my passport",
    "bank_statement": "here is my bank statement",
    "employment_letter": "here is my employment letter",
    "cas": "here is my cas number",
    "cos": "here is my cos number",
    "english_test": "here is my english test",
    "tb_certificate": "here is my tb test",
    "marriage_certificate": "here is my marriage certificate",
    "accommodation": "here is my tenancy agreement",
    "invitation_letter": "here is my invitation letter",
    "relationship_evidence": "here is my relationship evidence",
    "itinerary": "here is my itinerary",
}

REQ_KEYWORD = {
    "visitor.passport": "passport", "visitor.funds": "funds",
    "student.passport": "passport", "student.cas": "cas", "student.funds.28day": "funds",
    "worker.passport": "passport", "worker.cos": "cos", "worker.english": "english",
    "worker.funds": "funds",
    "spouse.passport": "passport", "spouse.relationship": "marriage",
    "spouse.financial.income": "income", "spouse.english": "english",
    "spouse.genuine": "genuine",
}
VERDICT_KEYWORD = {"MISSING": "provide", "INCONSISTENT": "mismatch", "EXPIRING": "expires"}


def _keywords(gap_item):
    req, verdict = gap_item["req_id"], gap_item["verdict"]
    kws = [REQ_KEYWORD.get(req, req.split(".")[-1])]
    if verdict == "INVALID":
        kws.append("below" if ("funds" in req or "income" in req) else "scanned")
    elif verdict in VERDICT_KEYWORD:
        kws.append(VERDICT_KEYWORD[verdict])
    return kws


def client_send(subject, body, attachments=None, mid=None, references=None):
    m = EmailMessage()
    m["From"] = CLIENT
    m["To"] = AGENT
    m["Subject"] = subject
    m["Message-ID"] = mid
    if references:
        m["References"] = references
    m.set_content(body)
    for p in attachments or []:
        m.add_attachment(Path(p).read_bytes(), maintype="application",
                         subtype="pdf", filename=Path(p).name)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.starttls()
        s.login(CLIENT, CLIENT_PASS)
        s.send_message(m)


def _raw(msgdata):
    for item in msgdata:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            return item[1]
    return None


def drain(adapter, gateway, subject):
    """Poll the agent inbox for UNSEEN mail with our subject, process, reply."""
    replies = []
    conn = imaplib.IMAP4_SSL(adapter.imap_host, adapter.imap_port)
    conn.login(adapter.imap_user, adapter.imap_password)
    conn.select("INBOX")
    typ, data = conn.search(None, f'(UNSEEN SUBJECT "{subject}")')
    if typ == "OK" and data and data[0]:
        for num in data[0].split():
            _, msgdata = conn.fetch(num, "(RFC822)")
            raw = _raw(msgdata)
            if not raw:
                continue
            msg = adapter.receive_email(raw)
            if msg:
                reply = gateway.handle(msg)
                adapter.send(reply, to_addr=CLIENT)
                replies.append(reply)
            conn.store(num, "+FLAGS", "\\Seen")
    conn.logout()
    return replies


def verify_client_inbox(subject, expected_keywords):
    """Confirm the reply reached the client inbox, threaded, with right content."""
    time.sleep(6)
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    conn.login(CLIENT, CLIENT_PASS)
    conn.select("INBOX")
    typ, data = conn.search(None, f'SUBJECT "Re: {subject}"')
    problems = []
    if typ != "OK" or not data or not data[0]:
        problems.append("no reply found in client inbox")
        conn.logout()
        return problems
    # fetch the newest reply
    nums = data[0].split()
    _, msgdata = conn.fetch(nums[-1], "(RFC822)")
    raw = _raw(msgdata)
    conn.logout()
    if not raw:
        return ["could not read reply"]
    from uk_visa_consultant.channels.email import parse_email
    parsed = parse_email(raw)
    flat = " ".join(parsed.body.split()).lower()
    for kw in expected_keywords:
        if kw not in flat:
            problems.append(f"reply missing keyword {kw!r}")
    return problems


def run_case(meta, case_dir):
    n = meta["case_id"].rsplit("_", 1)[-1]
    subject = f"e2e-{meta['visa_type']}-{n}"
    root = f"<{subject}-r@e2e>"
    adapter = EmailAdapter()
    gw = Gateway()
    last_reply = None

    client_send(subject, f"I want a {meta['visa_type']} visa", mid=f"<{subject}-r@e2e>")
    time.sleep(5)
    drain(adapter, gw, subject)

    if meta["visa_type"] == "visitor" and meta["client"].get("stay_end"):
        client_send(subject, f"I'm staying until {meta['client']['stay_end']}",
                    mid=f"<{subject}-d@e2e>", references=root)
        time.sleep(5)
        drain(adapter, gw, subject)

    for i, doc in enumerate(meta["documents"]):
        body = DOC_BODY.get(doc["doc_type"], "here is my document")
        client_send(subject, body, attachments=[case_dir / doc["file"]],
                    mid=f"<{subject}-d{i}@e2e>", references=root)
        time.sleep(5)
        replies = drain(adapter, gw, subject)
        if replies:
            last_reply = replies[-1]

    return subject, last_reply, meta


def main() -> int:
    route = sys.argv[1] if len(sys.argv) > 1 else "all"
    cases = sorted(Path("data/corpus").glob("*/*/case.json"))
    if route != "all":
        cases = [c for c in cases if c.parent.parent.name == route]

    passed = 0
    for case_json in cases:
        meta = json.loads(case_json.read_text())
        subject, last_reply, _ = run_case(meta, case_json.parent)
        flat = " ".join(last_reply.body.split()).lower() if last_reply else ""
        expected = meta["expected"]
        problems = []
        if expected["status"] == "READY":
            if "ready to submit" not in flat:
                problems.append("expected READY")
        else:
            for g in expected["gap_items"]:
                for kw in _keywords(g):
                    if kw not in flat:
                        problems.append(f"{g['req_id']}/{g['verdict']} missing {kw!r}")

        # also verify it actually reached the CLIENT inbox, threaded
        exp_kws = (["ready to submit"] if expected["status"] == "READY"
                   else [k for g in expected["gap_items"] for k in _keywords(g)])
        inbox_problems = verify_client_inbox(subject, exp_kws)
        problems += [f"inbox: {p}" for p in inbox_problems]

        ok = not problems
        if ok:
            passed += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {meta['case_id']}")
        for p in problems:
            print(f"           {p}")

    print(f"\n{passed}/{len(cases)} real-email E2E cases passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
