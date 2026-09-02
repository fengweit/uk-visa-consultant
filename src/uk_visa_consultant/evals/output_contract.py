"""Output contract — format checks for every output the system produces.

These validators are the "controlled and expectable" guarantee: every output
(GapReport, Package, Document, reply text) must conform to a fixed contract.
Used both at runtime (the Gateway gates replies before they ship) and by the
output harness (scripts/check_outputs.py). Each returns a list of violation
strings; empty == clean.
"""
from __future__ import annotations

from uk_visa_consultant.models import Document, GapReport, Package, RequirementSet

VALID_VERDICTS = {"OK", "MISSING", "INVALID", "INCONSISTENT", "EXPIRING"}
VALID_STATUSES = {"READY", "INCOMPLETE", "BLOCKED"}
VALID_GATE_VERDICTS = {"PASS", "FAIL", "HOLD"}
_REPLY_MAX_CHARS = 2000


def validate_gap_report(gap: GapReport, requirement_set: RequirementSet) -> list[str]:
    v: list[str] = []
    if gap.status not in VALID_STATUSES:
        v.append(f"gap.status={gap.status!r} invalid")
    valid_ids = {r.req_id for r in requirement_set.requirements}
    for item in gap.items:
        if item.verdict not in VALID_VERDICTS:
            v.append(f"{item.req_id}: verdict {item.verdict!r} invalid")
        if item.req_id not in valid_ids:
            v.append(f"{item.req_id}: unknown req_id")
        if item.verdict != "OK" and not (item.action or item.evidence):
            v.append(f"{item.req_id}: non-OK verdict with no action/evidence")
    return v


def validate_package(pkg: Package) -> list[str]:
    v: list[str] = []
    if not pkg.form_data:
        v.append("package.form_data empty")
    if not pkg.cover_letter.get("text"):
        v.append("package.cover_letter missing text")
    if not pkg.cover_letter.get("template"):
        v.append("package.cover_letter missing template")
    for c in pkg.checks:
        if c.verdict not in VALID_GATE_VERDICTS:
            v.append(f"{c.check_id}: gate verdict {c.verdict!r} invalid")
    if pkg.checks and all(c.verdict == "PASS" for c in pkg.checks):
        missing = [e.get("req_id") for e in pkg.checklist if e.get("status") != "included"]
        if missing:
            v.append(f"gates PASS but checklist missing: {missing}")
    return v


def validate_document(doc: Document) -> list[str]:
    v: list[str] = []
    if not doc.type:
        v.append("document.type empty")
    if not doc.source_path:
        v.append("document.source_path empty")
    return v


def validate_reply(body: str) -> list[str]:
    v: list[str] = []
    if not body or not body.strip():
        v.append("reply empty")
    if "traceback" in body.lower():
        v.append("reply contains a traceback")
    if len(body) > _REPLY_MAX_CHARS:
        v.append(f"reply too long ({len(body)} chars)")
    return v
