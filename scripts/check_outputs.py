"""Output harness — run the system and check every output against the contract.

1. Full corpus workflow -> validate every GapReport, Package, and Document.
2. Chaos messages -> validate every reply (through the gated Gateway).
Reports through the eval harness (promotion bar).

Usage:
    uv run python scripts/check_outputs.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uk_visa_consultant.evals.harness import run
from uk_visa_consultant.evals.output_contract import (
    validate_document, validate_gap_report, validate_package, validate_reply,
)
from uk_visa_consultant.gateway.loop import Gateway
from uk_visa_consultant.models import Channel, Message
from uk_visa_consultant.parsing.pipeline import intake
from uk_visa_consultant.visas import get_requirement_set
from uk_visa_consultant.workflow.supervisor import CaseSupervisor

CHAOS = [
    "", "   ", "hello", "thanks", "what's the weather today?",
    "plz help me get a visa", "im applying 4 student visa", "u there?",
    "I want a student visa", "visitor visa please", "skilled worker visa",
    "my wife needs a spouse visa", "here is my passport",
    "sending you my bank statement now", "what documents do I need?",
    "do I need a TB test?", "why was my application rejected?",
    "what's the status?", "I want to speak to a human", "this is a complaint",
    "can I come to the UK?", "help", "visa", "??", "12345", "£$%^&",
    "visa visa visa visa visa", "我要申请英国学生签证", "quiero una visa",
    "I want a student visa 😊👍", "I WANT A STUDENT VISA!!!",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/corpus")
    args = ap.parse_args()

    cases: list[tuple[str, str, str]] = []
    supervisor = CaseSupervisor()

    for case_json in sorted(Path(args.out).glob("*/*/case.json")):
        meta = json.loads(case_json.read_text())
        client = dict(meta["client"])
        client["application_date"] = meta.get("application_date")
        req = get_requirement_set(meta["visa_type"])
        docs = [intake(case_json.parent / d["file"], d.get("mime"), claimed_type=d.get("doc_type"))
                for d in meta["documents"]]
        result = supervisor.run(docs, req, client)

        v = validate_gap_report(result.gap_report, req)
        if result.package:
            v += validate_package(result.package)
        for d in result.documents:
            v += validate_document(d)
        cases.append((meta["case_id"], "clean", "clean" if not v else "; ".join(v)))

    gw = Gateway()
    for i, text in enumerate(CHAOS):
        reply = gw.handle(Message(id=f"m{i}", client_id=f"c{i}", channel=Channel.LOCAL, body=text)).body
        v = validate_reply(reply)
        cases.append((f"chaos:{text[:24]!r}", "clean", "clean" if not v else "; ".join(v)))

    report = run("output_contract", cases)
    print(report)
    for fid, exp, act in report.failures:
        print(f"  FAIL {fid}: {act}")
    return 0 if report.promoted else 1


if __name__ == "__main__":
    sys.exit(main())
