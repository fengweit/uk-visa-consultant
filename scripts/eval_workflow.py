"""Run the agent workflow over the corpus and check final outcomes vs expected.

For each case: parse every document (intake, deterministic field fallback), run
the CaseSupervisor (intake → gathering → review), and compare the resulting
GapReport (status + failing verdicts) against case.json `expected`. This is the
end-to-end eval of the agent workflow — the deterministic spine, no DeepSeek.

Usage:
    uv run python scripts/eval_workflow.py [--out data/corpus] [--fail]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uk_visa_consultant.evals.harness import run
from uk_visa_consultant.parsing.pipeline import intake
from uk_visa_consultant.visas import get_requirement_set
from uk_visa_consultant.workflow.supervisor import CaseSupervisor


def _expected_str(expected: dict) -> str:
    gaps = ",".join(sorted(f"{g['req_id']}:{g['verdict']}" for g in expected.get("gap_items", [])))
    return expected.get("status", "") + (f":{gaps}" if gaps else "")


def _actual_str(gap) -> str:
    gaps = ",".join(sorted(f"{i.req_id}:{i.verdict}" for i in gap.items if i.verdict != "OK"))
    return gap.status + (f":{gaps}" if gaps else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/corpus")
    ap.add_argument("--fail", action="store_true", help="exit non-zero on any failure")
    args = ap.parse_args()

    supervisor = CaseSupervisor()
    cases: list[tuple[str, str, str]] = []
    for case_json in sorted(Path(args.out).glob("*/*/case.json")):
        meta = json.loads(case_json.read_text())
        docs = [intake(case_json.parent / d["file"], d.get("mime"), claimed_type=d.get("doc_type"))
                for d in meta["documents"]]
        result = supervisor.run(docs, get_requirement_set(meta["visa_type"]), meta["client"])
        cases.append((meta["case_id"], _expected_str(meta["expected"]), _actual_str(result.gap_report)))

    report = run("agent_workflow", cases)
    print(report)
    for fid, exp, act in report.failures:
        print(f"  FAIL {fid}:\n    expected {exp}\n    actual   {act}")
    return 0 if report.promoted else 1


if __name__ == "__main__":
    sys.exit(main())
