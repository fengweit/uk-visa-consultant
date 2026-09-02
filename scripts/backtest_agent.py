"""Backtest the intake agent (intent -> intake) over the generated corpus.

For every document in the corpus, sends a submit_document message with that PDF
attached through IntakeAgent and checks the resulting Document against the
ground-truth case.json (type for text docs, scanned flag for image-only docs).

Usage:
    uv run python scripts/backtest_agent.py [--out data/corpus]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uk_visa_consultant.agent import IntakeAgent
from uk_visa_consultant.evals.harness import run
from uk_visa_consultant.models import Attachment, Channel, Message


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/corpus")
    args = ap.parse_args()

    agent = IntakeAgent()
    cases: list[tuple[str, str, str]] = []
    root = Path(args.out)

    for case_json in sorted(root.glob("*/*/case.json")):
        meta = json.loads(case_json.read_text())
        for doc in meta["documents"]:
            pdf = case_json.parent / doc["file"]
            msg = Message(
                id=f"bt_{meta['case_id']}_{doc['file']}",
                client_id="c_backtest",
                channel=Channel.LOCAL,
                body="here is my document, please check it",
                attachments=[Attachment(kind="pdf", local_path=str(pdf), mime="application/pdf")],
            )
            result = agent.handle(msg)

            if doc.get("scanned"):
                actual = "scanned" if (result.documents and result.documents[0].quality.scanned) else "not_scanned"
                expected = "scanned"
            else:
                actual = result.documents[0].type if result.documents else "no_document"
                expected = doc["doc_type"]
            cases.append((f"{meta['case_id']}/{doc['file']}", expected, actual))

    report = run("intake_agent", cases)
    print(report)
    for fid, exp, act in report.failures:
        print(f"  FAIL {fid}: expected {exp}, got {act}")
    return 0 if report.promoted else 1


if __name__ == "__main__":
    sys.exit(main())
