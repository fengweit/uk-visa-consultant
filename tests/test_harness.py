"""Eval harness: promotion bar behaviour."""
from uk_visa_consultant.evals.harness import run


def test_harness_promotes_on_full_pass():
    report = run("intent", [
        ("a", "submit_document", "submit_document"),
        ("b", "document_query", "document_query"),
    ])
    assert report.passed == 2
    assert report.promoted is True


def test_harness_blocks_on_failures():
    report = run("intent", [
        ("a", "submit_document", "document_query"),
        ("b", "document_query", "document_query"),
    ], bar=1.0)
    assert report.promoted is False
    assert len(report.failures) == 1
    assert report.pass_rate == 0.5
