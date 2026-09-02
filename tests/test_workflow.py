"""Gap analysis + supervisor — the deterministic workflow spine (no network)."""
from uk_visa_consultant.gaps.gap import analyze
from uk_visa_consultant.models import Document, DocumentQuality
from uk_visa_consultant.visas import SPOUSE, STUDENT, VISITOR, WORKER
from uk_visa_consultant.workflow.supervisor import CaseSupervisor


def _doc(dtype, fields=None, scanned=False):
    return Document(id=f"d_{dtype}", type=dtype, source_path=f"/x/{dtype}.pdf",
                    fields=fields or {}, quality=DocumentQuality(scanned=scanned))


def _verdicts(gap):
    return {i.req_id: i.verdict for i in gap.items}


def test_student_complete_ready():
    docs = [_doc("passport", {"full_name": "Jane Doe"}),
            _doc("cas", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 18420.0, "min_balance": 15200.0})]
    assert analyze(docs, STUDENT, {"name": "Jane Doe"}).status == "READY"


def test_student_missing_cas():
    docs = [_doc("passport", {"full_name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 18420.0, "min_balance": 15200.0})]
    gap = analyze(docs, STUDENT, {"name": "Jane Doe"})
    assert _verdicts(gap)["student.cas"] == "MISSING"
    assert gap.status == "INCOMPLETE"


def test_student_funds_insufficient():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cas", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 8000.0, "min_balance": 7500.0})]
    assert _verdicts(analyze(docs, STUDENT, {"name": "Jane Doe"}))["student.funds.28day"] == "INVALID"


def test_student_funds_28day_violation():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cas", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 15000.0, "min_balance": 2000.0})]
    assert _verdicts(analyze(docs, STUDENT, {"name": "Jane Doe"}))["student.funds.28day"] == "INVALID"


def test_student_name_mismatch():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cas", {"name": "Jane A. Doe"}),
            _doc("bank_statement", {"closing_balance": 18420.0, "min_balance": 15200.0})]
    assert _verdicts(analyze(docs, STUDENT, {"name": "Jane Doe"}))["student.cas"] == "INCONSISTENT"


def test_worker_missing_english():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cos", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 5000.0, "min_balance": 4800.0})]
    assert _verdicts(analyze(docs, WORKER, {"name": "Jane Doe"}))["worker.english"] == "MISSING"


def test_worker_funds_insufficient():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cos", {"name": "Jane Doe"}),
            _doc("english_test", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 900.0, "min_balance": 850.0})]
    assert _verdicts(analyze(docs, WORKER, {"name": "Jane Doe"}))["worker.funds"] == "INVALID"


def test_spouse_income_below():
    docs = [_doc("passport", {"full_name": "Jane Doe"}),
            _doc("marriage_certificate", {"spouse_a": "Jane Doe", "spouse_b": "David Roe"}),
            _doc("employment_letter", {"salary": 20000.0}),
            _doc("english_test", {"name": "Jane Doe"}),
            _doc("relationship_evidence", {})]
    assert _verdicts(analyze(docs, SPOUSE, {"name": "Jane Doe"}))["spouse.financial.income"] == "INVALID"


def test_spouse_missing_genuine():
    docs = [_doc("passport", {"full_name": "Jane Doe"}),
            _doc("marriage_certificate", {"spouse_a": "Jane Doe", "spouse_b": "David Roe"}),
            _doc("employment_letter", {"salary": 35000.0}),
            _doc("english_test", {"name": "Jane Doe"})]
    assert _verdicts(analyze(docs, SPOUSE, {"name": "Jane Doe"}))["spouse.genuine"] == "MISSING"


def test_visitor_passport_expiring():
    docs = [_doc("passport", {"full_name": "Jane Doe", "expiry": "2026-09-25"}),
            _doc("bank_statement", {"account_holder": "Jane Doe"}),
            _doc("accommodation", {})]
    gap = analyze(docs, VISITOR, {"name": "Jane Doe", "stay_end": "2026-10-05"})
    assert _verdicts(gap)["visitor.passport"] == "EXPIRING"


def test_visitor_scanned_passport():
    docs = [_doc("passport", {"full_name": "Jane Doe"}, scanned=True),
            _doc("bank_statement", {"account_holder": "Jane Doe"}),
            _doc("accommodation", {})]
    gap = analyze(docs, VISITOR, {"name": "Jane Doe", "stay_end": "2026-10-05"})
    assert _verdicts(gap)["visitor.passport"] == "INVALID"


def test_supervisor_ready_to_review():
    docs = [_doc("passport", {"full_name": "Jane Doe"}), _doc("cas", {"name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 18420.0, "min_balance": 15200.0})]
    assert CaseSupervisor().run(docs, STUDENT, {"name": "Jane Doe"}).final_state == "review"


def test_supervisor_incomplete_stays_gathering():
    docs = [_doc("passport", {"full_name": "Jane Doe"}),
            _doc("bank_statement", {"closing_balance": 18420.0, "min_balance": 15200.0})]
    assert CaseSupervisor().run(docs, STUDENT, {"name": "Jane Doe"}).final_state == "gathering"
