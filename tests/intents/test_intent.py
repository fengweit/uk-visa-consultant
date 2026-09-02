"""Intent recognition golden set (docs/specs/intent-recognition.md)."""
from uk_visa_consultant.intents.intent import IntentRecognizer


def _rec(text):
    return IntentRecognizer().recognize(text)


def test_submit_passport():
    i = _rec("here is my passport")
    assert i.intent == "submit_document"
    assert i.matched_rule == "submit_document.v1"
    assert i.slots.get("document_type") == "passport"


def test_submit_bank_statement():
    i = _rec("sending you my bank statement now")
    assert i.intent == "submit_document"
    assert i.slots.get("document_type") == "bank_statement"


def test_document_query():
    i = _rec("what documents do I need?")
    assert i.intent == "document_query"
    assert i.matched_rule == "document_query.v1"


def test_document_query_do_i_need_tb():
    i = _rec("do I need a TB test?")
    assert i.intent == "document_query"


def test_gap_question():
    i = _rec("why was my application rejected?")
    assert i.intent == "gap_question"


def test_status_check():
    i = _rec("what is the status of my application")
    assert i.intent == "status_check"


def test_schedule():
    i = _rec("can I book a biometrics appointment")
    assert i.intent == "schedule"


def test_escalate_human():
    i = _rec("I want to speak to a human please")
    assert i.intent == "escalate_human"


def test_general_fallback_clarifies():
    i = _rec("the weather is nice today")
    assert i.intent == "general"
    assert i.needs_clarification is True


def test_deterministic():
    r = IntentRecognizer()
    assert r.recognize("here is my passport") == r.recognize("here is my passport")
