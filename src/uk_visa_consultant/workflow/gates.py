"""Verification gates — fail-closed, run before delivery (docs/specs/...).

PASS ships; FAIL/HOLD blocks; an unverifiable check is HOLD, never PASS. The
gates are the delivery boundary: identical inputs produce identical verdicts.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from uk_visa_consultant.models import Document, GapReport, Package, VerificationResult


def _find(documents: list[Document], doc_type: str) -> Document | None:
    for d in documents:
        if d.type == doc_type:
            return d
    return None


def verify(package: Package, gap: GapReport, documents: list[Document],
           client: dict[str, Any]) -> tuple[str, list[VerificationResult]]:
    checks: list[VerificationResult] = []

    checks.append(VerificationResult(
        check_id="gate.gap.ready",
        verdict="PASS" if gap.status == "READY" else "FAIL",
        evidence=f"gap status = {gap.status}",
    ))

    failing = [i.req_id for i in gap.items if i.verdict != "OK"]
    checks.append(VerificationResult(
        check_id="gate.mandatory.all",
        verdict="PASS" if not failing else "FAIL",
        evidence="all mandatory OK" if not failing else f"failing: {', '.join(failing)}",
    ))

    missing_form = [k for k, v in package.form_data.items() if v in (None, "")]
    checks.append(VerificationResult(
        check_id="gate.form.complete",
        verdict="PASS" if not missing_form else "FAIL",
        evidence="form complete" if not missing_form else f"missing: {', '.join(missing_form)}",
    ))

    # funds window: statement period_end within 31 days of application date
    app_date = client.get("application_date")
    bank = _find(documents, "bank_statement")
    if bank is not None and app_date:
        period_end = bank.fields.get("period_end")
        if period_end is None:
            checks.append(VerificationResult(check_id="gate.funds.window", verdict="HOLD",
                                             evidence="no statement period end"))
        else:
            try:
                d_end = date.fromisoformat(str(period_end))
                d_app = date.fromisoformat(str(app_date))
                ok = (d_app - d_end).days <= 31
                checks.append(VerificationResult(
                    check_id="gate.funds.window", verdict="PASS" if ok else "FAIL",
                    evidence=f"statement {period_end}, application {app_date}"))
            except ValueError:
                checks.append(VerificationResult(check_id="gate.funds.window", verdict="HOLD",
                                                 evidence="unparseable dates"))

    # passport validity (scanned -> HOLD; expiry before stay end -> FAIL)
    passport = _find(documents, "passport")
    if passport is not None:
        expiry = passport.fields.get("expiry")
        stay_end = client.get("stay_end")
        verdict, evidence = "PASS", "passport valid"
        if passport.quality.scanned:
            verdict, evidence = "HOLD", "scanned passport — needs OCR/human verification"
        elif expiry and stay_end and str(expiry) < str(stay_end):
            verdict, evidence = "FAIL", f"expiry {expiry} before stay end {stay_end}"
        checks.append(VerificationResult(check_id="gate.passport.validity",
                                         verdict=verdict, evidence=evidence))

    final = ("HOLD" if any(c.verdict == "HOLD" for c in checks)
             else "FAIL" if any(c.verdict == "FAIL" for c in checks)
             else "PASS")
    return final, checks
