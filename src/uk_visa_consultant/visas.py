"""Visa RequirementSet data — the "data, not model judgment" layer.

Each route lists its enforced requirements as (req_id, doc_type, checks, params).
The GapAgent (gaps/gap.py) turns these into deterministic verdicts. Thresholds
are the verified figures (see docs/visas + memory): student maintenance
£1,171/mo outside London × 9 = £10,539; Skilled Worker £1,270; spouse income
£29,000.
"""
from __future__ import annotations

from uk_visa_consultant.models import Requirement, RequirementSet


def _req(req_id, name, doc_type, checks, mandatory=True, **params):
    return Requirement(req_id=req_id, name=name, mandatory=mandatory,
                       rules={"doc_type": doc_type, "checks": checks, **params})


VISITOR = RequirementSet(
    visa_type="visitor", route="Standard Visitor",
    requirements=[
        _req("visitor.passport", "Passport", "passport", ["presence", "expiry", "scanned"]),
        _req("visitor.funds", "Proof of funds", "bank_statement",
             ["presence", "name_consistency"], name_field="account_holder"),
        _req("visitor.accommodation", "Accommodation", "accommodation", ["presence"]),
    ],
)

STUDENT = RequirementSet(
    visa_type="student", route="Student Route",
    requirements=[
        _req("student.passport", "Passport", "passport", ["presence"]),
        _req("student.cas", "CAS", "cas", ["presence", "name_consistency"], name_field="name"),
        _req("student.funds.28day", "Maintenance funds (28-day)", "bank_statement",
             ["presence", "funds_min"], min=10539.0),
    ],
)

WORKER = RequirementSet(
    visa_type="worker", route="Skilled Worker",
    requirements=[
        _req("worker.passport", "Passport", "passport", ["presence"]),
        _req("worker.cos", "CoS", "cos", ["presence", "name_consistency"], name_field="name"),
        _req("worker.english", "English language", "english_test", ["presence"]),
        _req("worker.funds", "Maintenance funds", "bank_statement", ["presence", "funds_min"], min=1270.0),
    ],
)

SPOUSE = RequirementSet(
    visa_type="spouse", route="Spouse / Partner",
    requirements=[
        _req("spouse.passport", "Passport", "passport", ["presence"]),
        _req("spouse.relationship", "Marriage certificate", "marriage_certificate",
             ["presence", "name_consistency"], name_field="spouse_a"),
        _req("spouse.financial.income", "Sponsor income", "employment_letter",
             ["presence", "income_min"], min=29000.0),
        _req("spouse.english", "English language", "english_test", ["presence"]),
        _req("spouse.genuine", "Genuine relationship evidence", "relationship_evidence", ["presence"]),
    ],
)

REQUIREMENT_SETS = {"visitor": VISITOR, "student": STUDENT, "worker": WORKER, "spouse": SPOUSE}


def get_requirement_set(visa_type: str) -> RequirementSet:
    return REQUIREMENT_SETS.get(visa_type, RequirementSet(visa_type=visa_type, route=visa_type))
