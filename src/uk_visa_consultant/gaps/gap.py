"""Gap analysis — Documents × RequirementSet → GapReport (deterministic).

docs/specs/gap-analysis.md: verdicts are computed, never model-generated. This
is the `gathering`-state handler. Presence, funds/income thresholds, name
consistency, expiry, and scanned detection are all deterministic here; the
human-readable evidence/action prose stays separate.
"""
from __future__ import annotations

from typing import Any

from uk_visa_consultant.models import Document, GapItem, GapReport, RequirementSet


def _find(documents: list[Document], doc_type: str) -> Document | None:
    for d in documents:
        if d.type == doc_type:
            return d
    return None


def _ref_name(documents: list[Document], client: dict[str, Any]) -> str | None:
    passport = _find(documents, "passport")
    if passport and passport.fields.get("full_name"):
        return passport.fields["full_name"]
    return client.get("name")


def analyze(documents: list[Document], requirement_set: RequirementSet,
            client: dict[str, Any]) -> GapReport:
    ref_name = _ref_name(documents, client)
    items: list[GapItem] = []

    for req in requirement_set.requirements:
        rules = req.rules
        doc = _find(documents, rules.get("doc_type", ""))
        checks = rules.get("checks", ["presence"])

        if doc is None:
            if req.mandatory:
                items.append(GapItem(req_id=req.req_id, req_name=req.name, verdict="MISSING",
                                     action=f"Provide your {req.name.lower()}.",
                                     severity="mandatory"))
            continue

        verdict = "OK"
        action = None
        for check in checks:
            if check == "presence":
                continue
            if check == "name_consistency":
                actual = doc.fields.get(rules.get("name_field", ""))
                if actual and ref_name and str(actual).strip().lower() != str(ref_name).strip().lower():
                    verdict = "INCONSISTENT"
                    action = f"Name mismatch: '{actual}' vs passport '{ref_name}'."
            elif check == "funds_min":
                m = rules["min"]
                closing = doc.fields.get("closing_balance")
                minbal = doc.fields.get("min_balance")
                if closing is None or closing < m or (minbal is not None and minbal < m):
                    verdict = "INVALID"
                    action = f"Funds below required £{m:,.0f}."
            elif check == "income_min":
                m = rules["min"]
                salary = doc.fields.get("salary")
                if salary is None or salary < m:
                    verdict = "INVALID"
                    action = f"Income below required £{m:,.0f}."
            elif check == "expiry":
                stay_end = client.get("stay_end")
                expiry = doc.fields.get("expiry")
                if stay_end and expiry and str(expiry) < str(stay_end):
                    verdict = "EXPIRING"
                    action = f"Expires {expiry}, before stay end {stay_end}."
            elif check == "scanned":
                if doc.quality.scanned and not doc.quality.ocr_used:
                    verdict = "INVALID"
                    action = "Scanned document needs OCR."

        items.append(GapItem(req_id=req.req_id, req_name=req.name, doc_id=doc.id, verdict=verdict,
                             action=action, severity="mandatory" if req.mandatory else "recommended"))

    status = "READY" if all(i.verdict == "OK" for i in items) else "INCOMPLETE"
    return GapReport(client_id=str(client.get("id", "")), visa_type=requirement_set.visa_type,
                     status=status, items=items)
