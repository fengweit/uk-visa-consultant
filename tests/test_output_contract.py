"""Output contract validators (format checks)."""
from uk_visa_consultant.evals.output_contract import (
    validate_gap_report, validate_package, validate_reply,
)
from uk_visa_consultant.models import GapItem, GapReport, Package, VerificationResult
from uk_visa_consultant.visas import STUDENT


def test_validate_reply_clean():
    assert validate_reply("I can help with your Student Route application.") == []


def test_validate_reply_rejects_empty_and_traceback():
    assert validate_reply("") != []
    assert validate_reply("   ") != []
    assert validate_reply("Traceback (most recent call last): ...") != []


def test_validate_gap_report_clean():
    gap = GapReport(client_id="c1", visa_type="student", status="INCOMPLETE",
                    items=[GapItem(req_id="student.cas", req_name="CAS",
                                   verdict="MISSING", action="Provide your cas.")])
    assert validate_gap_report(gap, STUDENT) == []


def test_validate_gap_report_rejects_bad_verdict():
    gap = GapReport(client_id="c1", visa_type="student", status="INCOMPLETE",
                    items=[GapItem(req_id="student.cas", req_name="CAS", verdict="WEIRD")])
    assert validate_gap_report(gap, STUDENT) != []


def test_validate_gap_report_rejects_unknown_req_id():
    gap = GapReport(client_id="c1", visa_type="student", status="INCOMPLETE",
                    items=[GapItem(req_id="ghost.req", req_name="X", verdict="MISSING",
                                   action="do something")])
    assert validate_gap_report(gap, STUDENT) != []


def test_validate_package_clean():
    pkg = Package(package_id="p1", client_id="c1", visa_type="student",
                  form_data={"name": "Jane Doe"},
                  cover_letter={"template": "cover.student.v1", "text": "hello"},
                  checklist=[{"req_id": "student.cas", "status": "included"}],
                  checks=[VerificationResult(check_id="gate.gap.ready", verdict="PASS")])
    assert validate_package(pkg) == []


def test_validate_package_rejects_missing_cover_letter():
    pkg = Package(package_id="p1", client_id="c1", visa_type="student",
                  form_data={"name": "Jane Doe"})
    assert validate_package(pkg) != []
