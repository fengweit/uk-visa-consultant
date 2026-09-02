"""Run ALL corpus cases through the full email+PDF pipeline and verify the
agent's final reply matches each case's expected outcome.

For each of the 20 cases: send the route message, then each document as a real
MIME email with its PDF attached, and assert the final reply reflects the
ground-truth `expected` (status + failing requirements).

Usage:
    uv run python scripts/e2e_corpus.py
"""
from __future__ import annotations

import json
import sys
from email.message import EmailMessage
from pathlib import Path

from uk_visa_consultant.channels.email import EmailAdapter
from uk_visa_consultant.gateway.loop import Gateway

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
    "visitor.passport": "passport",
    "visitor.funds": "funds",
    "student.passport": "passport",
    "student.cas": "cas",
    "student.funds.28day": "funds",
    "worker.passport": "passport",
    "worker.cos": "cos",
    "worker.english": "english",
    "worker.funds": "funds",
    "spouse.passport": "passport",
    "spouse.relationship": "marriage",
    "spouse.financial.income": "income",
    "spouse.english": "english",
    "spouse.genuine": "genuine",
}

VERDICT_KEYWORD = {
    "MISSING": "provide",
    "INCONSISTENT": "mismatch",
    "EXPIRING": "expires",
}


def _email(from_addr, to, body, attachment, mid):
    m = EmailMessage()
    m["From"] = from_addr
    m["To"] = to
    m["Subject"] = "doc"
    m["Message-ID"] = mid
    m.set_content(body)
    if attachment:
        m.add_attachment(Path(attachment).read_bytes(), maintype="application",
                         subtype="pdf", filename=Path(attachment).name)
    return m.as_bytes()


def _keywords(gap_item):
    req = gap_item["req_id"]
    verdict = gap_item["verdict"]
    kws = [REQ_KEYWORD.get(req, req.split(".")[-1])]
    if verdict == "INVALID":
        kws.append("below" if ("funds" in req or "income" in req) else "scanned")
    elif verdict in VERDICT_KEYWORD:
        kws.append(VERDICT_KEYWORD[verdict])
    return kws


def run_case(meta, case_dir):
    adapter = EmailAdapter(imap_host="x", imap_user="u", imap_password="p",
                           from_addr="visa@example.com",
                           seen_path=f"/tmp/e2e_seen_{meta['case_id']}.json")
    gw = Gateway()
    client = "client@example.com"
    reply = gw.handle(adapter.receive_email(
        _email(client, "visa@example.com", f"I want a {meta['visa_type']} visa", None,
               f"<{meta['case_id']}-r@x>")))
    if meta["visa_type"] == "visitor" and meta["client"].get("stay_end"):
        reply = gw.handle(adapter.receive_email(
            _email(client, "visa@example.com",
                   f"I'm staying until {meta['client']['stay_end']}", None,
                   f"<{meta['case_id']}-dates@x>")))
    for i, doc in enumerate(meta["documents"]):
        body = DOC_BODY.get(doc["doc_type"], "here is my document")
        msg = adapter.receive_email(_email(
            client, "visa@example.com", body, case_dir / doc["file"],
            f"<{meta['case_id']}-{i}@x>"))
        reply = gw.handle(msg)
    return reply


def main() -> int:
    passed = 0
    total = 0
    for case_json in sorted(Path("data/corpus").glob("*/*/case.json")):
        meta = json.loads(case_json.read_text())
        total += 1
        reply = run_case(meta, case_json.parent)
        flat = " ".join(reply.body.split()).lower()
        expected = meta["expected"]
        problems = []

        if expected["status"] == "READY":
            if "ready to submit" not in flat:
                problems.append("expected READY but reply does not say ready to submit")
        else:
            if "ready to submit" in flat:
                problems.append("expected INCOMPLETE but reply says ready to submit")
            for g in expected["gap_items"]:
                for kw in _keywords(g):
                    if kw not in flat:
                        problems.append(f"{g['req_id']}/{g['verdict']}: keyword {kw!r} missing")

        ok = not problems
        if ok:
            passed += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {meta['case_id']:34} {flat[:76]}")
        for p in problems:
            print(f"           {p}")

    print(f"\n{passed}/{total} corpus cases produced correct replies")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
