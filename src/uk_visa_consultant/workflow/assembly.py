"""Assembly — the `review`-state handler (docs/specs/assembly-delivery-revision.md).

Static/deterministic: builds a submission-ready Package from Documents + a READY
GapReport + the client profile. No model in the assembly path.
"""
from __future__ import annotations

import hashlib
from typing import Any

from uk_visa_consultant.models import Document, GapReport, Package, RequirementSet


def _find(documents: list[Document], doc_type: str) -> Document | None:
    for d in documents:
        if d.type == doc_type:
            return d
    return None


def _form_data(client: dict[str, Any], documents: list[Document]) -> dict[str, Any]:
    """Application-form answers, traced to the client profile / extracted fields."""
    form: dict[str, Any] = {}
    for key in ("name", "dob", "nationality", "passport_no", "visa_type"):
        if client.get(key) is not None:
            form[key] = client[key]
    passport = _find(documents, "passport")
    if passport:
        for key in ("full_name", "dob", "passport_no", "nationality", "expiry"):
            if passport.fields.get(key) is not None:
                form[key] = passport.fields[key]
    return form


def _cover_letter(client: dict[str, Any], requirement_set: RequirementSet) -> dict[str, Any]:
    name = client.get("name", "the applicant")
    return {
        "template": f"cover.{requirement_set.visa_type}.v1",
        "text": (
            f"Dear Entry Clearance Officer,\n\n"
            f"I am applying under the {requirement_set.route} route. "
            f"My supporting documents are indexed alongside this letter.\n\n"
            f"Yours faithfully,\n{name}"
        ),
    }


def assemble(documents: list[Document], requirement_set: RequirementSet,
             gap: GapReport, client: dict[str, Any]) -> Package:
    checklist = []
    for req in requirement_set.requirements:
        doc = _find(documents, req.rules.get("doc_type", ""))
        checklist.append({"req_id": req.req_id, "doc_id": doc.id if doc else None,
                          "status": "included" if doc else "missing"})

    return Package(
        package_id="pkg_" + hashlib.sha256(str(client.get("name", "")).encode()).hexdigest()[:12],
        client_id=str(client.get("id", "")),
        visa_type=requirement_set.visa_type,
        form_data=_form_data(client, documents),
        checklist=checklist,
        cover_letter=_cover_letter(client, requirement_set),
        supporting=[d.id for d in documents],
    )
