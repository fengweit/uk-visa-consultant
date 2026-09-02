"""Smoke tests: shared contract is importable and behaves."""
from pydantic import BaseModel

from uk_visa_consultant.llm import StubLLMClient
from uk_visa_consultant.models import Channel, Document, Message


def test_message_roundtrip():
    m = Message(id="m1", client_id="c1", channel=Channel.LOCAL, body="hi")
    assert m.channel is Channel.LOCAL
    assert m.attachments == []


def test_document_defaults():
    d = Document(id="d1", type="passport", source_path="/tmp/x.pdf")
    assert d.quality.scanned is False
    assert d.fields == {}


def test_stub_llm_parses_schema():
    class R(BaseModel):
        closing_balance: float

    stub = StubLLMClient({"statement": {"closing_balance": 100.0}})
    res = stub.complete("bank statement text", schema=R)
    assert res.parsed.closing_balance == 100.0
    assert res.schema_errors == []


def test_stub_llm_fails_closed_on_bad_schema():
    class R(BaseModel):
        closing_balance: float

    stub = StubLLMClient({"statement": {"not_a_field": 1}})
    res = stub.complete("bank statement text", schema=R)
    assert res.parsed is None
    assert res.schema_errors != []


def test_llm_accepts_single_json_fence_but_rejects_prose():
    class R(BaseModel):
        status: str

    fenced = StubLLMClient({"probe": "```json\n{\"status\": \"ok\"}\n```"})
    good = fenced.complete("probe", schema=R)
    assert good.parsed is not None
    assert good.parsed.status == "ok"
    assert good.schema_errors == []

    prose = StubLLMClient({"probe": "Here is the result:\n```json\n{\"status\": \"ok\"}\n```"})
    bad = prose.complete("probe", schema=R)
    assert bad.parsed is None
    assert bad.schema_errors
