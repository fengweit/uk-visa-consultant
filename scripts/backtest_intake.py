"""Backtest the intake pipeline over the generated corpus.

For each case's documents it runs extraction (pdf-inspector) + intake() and
checks the deterministic layers against the ground-truth case.json:
- text documents: pdf_type == "text_based" AND matched type == expected doc_type
- scanned documents: pdf_type != "text_based" AND quality.scanned == True

Field extraction is the LLM layer (DeepSeek, not yet configured) and is out of
scope here; this backtests classification + typing deterministically.

Usage:
    uv run python scripts/backtest_intake.py [--out data/corpus] [--fail-on-mismatch]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uk_visa_consultant.parsing.extract import extract
from uk_visa_consultant.parsing.pipeline import intake


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/corpus")
    ap.add_argument("--fail-on-mismatch", action="store_true")
    args = ap.parse_args()

    root = Path(args.out)
    total = passed = 0
    failures: list[str] = []
    print(f"{'case':34} {'doc':18} {'expected':16} {'got':10} {'pdf_type':11} {'scanned':8} result")

    for case_json in sorted(root.glob("*/*/case.json")):
        meta = json.loads(case_json.read_text())
        case_id = meta["case_id"]
        for doc in meta["documents"]:
            total += 1
            pdf = case_json.parent / doc["file"]
            ext = extract(pdf, None)
            document = intake(pdf)
            expected = doc["doc_type"]
            scanned_expected = bool(doc.get("scanned", False))

            if scanned_expected:
                ok = ext.pdf_type != "text_based" and document.quality.scanned
            else:
                ok = ext.pdf_type == "text_based" and document.type == expected

            passed += ok
            if not ok:
                failures.append(
                    f"{case_id}/{doc['file']}: expected type={expected} scanned={scanned_expected}, "
                    f"got type={document.type} pdf_type={ext.pdf_type} scanned={document.quality.scanned}"
                )
            print(
                f"{case_id:34} {doc['file']:18} {expected:16} {document.type:10} "
                f"{ext.pdf_type:11} {str(document.quality.scanned):8} {'OK' if ok else 'FAIL'}"
            )

    print(f"\n{passed}/{total} checks passed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print("  -", f)
        if args.fail_on_mismatch:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
