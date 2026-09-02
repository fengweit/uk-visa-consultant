from types import SimpleNamespace
import importlib

from uk_visa_consultant.gaps.gap import analyze
from uk_visa_consultant.models import Document, DocumentQuality
from uk_visa_consultant.visas import get_requirement_set

extract_module = importlib.import_module("uk_visa_consultant.parsing.extract")


def test_image_ocr_populates_text_and_quality(monkeypatch, tmp_path):
    image = tmp_path / "passport.jpg"
    image.write_bytes(b"fake-image")
    monkeypatch.setattr(extract_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        extract_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="0.99\tPASSPORT\n0.94\tPassport No. 123456789\n",
        ),
    )
    ext = extract_module.extract_image_file(image)
    assert ext.ocr_used is True
    assert ext.pages_needing_ocr == []
    assert ext.full_text == "PASSPORT\nPassport No. 123456789"
    assert ext.metadata["ocr_engine"] == "macos-vision"
    assert ext.classification_confidence == 0.94


def test_ocr_success_clears_scanned_gap_but_failure_stays_blocked():
    reqs = get_requirement_set("visitor")
    client = {"id": "c", "stay_end": "2026-01-01"}
    other = [
        Document(id="bank", type="bank_statement", source_path="bank.pdf"),
        Document(id="stay", type="accommodation", source_path="stay.pdf"),
    ]
    fields = {"full_name": "DOE JOHN", "expiry": "2026-05-22"}
    passed = Document(
        id="p1", type="passport", source_path="passport.jpg", fields=fields,
        quality=DocumentQuality(scanned=True, ocr_used=True),
    )
    blocked = Document(
        id="p2", type="passport", source_path="passport.jpg", fields=fields,
        quality=DocumentQuality(scanned=True, ocr_used=False),
    )
    ok_report = analyze([passed, *other], reqs, client)
    bad_report = analyze([blocked, *other], reqs, client)
    ok_item = next(i for i in ok_report.items if i.req_id == "visitor.passport")
    bad_item = next(i for i in bad_report.items if i.req_id == "visitor.passport")
    assert ok_item.verdict == "OK"
    assert bad_item.verdict == "INVALID"
    assert "needs OCR" in (bad_item.action or "")
