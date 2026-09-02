"""Extraction layer: attachment -> per-page text + tables + metadata + scanned flag.

Engine: ``pdf-inspector`` (Rust bindings, v1.17+) — per
``docs/specs/document-parsing.md``. It classifies and extracts in one pass:

- ``process_pdf`` -> ``PdfResult``: ``pdf_type`` (``text_based`` | ``scanned`` |
  ``image_based`` | ``mixed``), 0-1 ``confidence``, ``page_count``, ``markdown``,
  ``pages_needing_ocr`` (1-based), ``pages_with_tables``, ``has_encoding_issues``,
  ``title``, ``is_complex_layout``.
- ``extract_text_with_positions`` -> ``TextItem[]`` (``page`` is 1-based) — the
  source of per-page plain text.
- ``extract_pages_markdown`` -> per-page Markdown (``page`` is 0-based) — used
  for table/region provenance.

OCR (``process_pdf_with_ocr``) is OUT OF SCOPE for the intake MVP (it needs the
PDFium/ONNX runtime); we record ``pages_needing_ocr`` and never set ``ocr_used``
until OCR is actually wired. Image-only pages are reported as ``scanned``, never
as empty "no content".
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pdf_inspector
from pydantic import BaseModel, Field

# pdf_type values that imply no usable text layer.
_SCANNED_TYPES = {"scanned", "image_based", "mixed"}


class PageContent(BaseModel):
    """One page of extracted content."""

    page: int  # 1-based
    text: str = ""
    markdown: str = ""
    has_text: bool = False
    needs_ocr: bool = False


class Extraction(BaseModel):
    """Raw output of the extraction layer; typing happens in the next layer."""

    source_path: str
    num_pages: int = 0
    pdf_type: str = "text_based"  # text_based | scanned | image_based | mixed
    classification_confidence: float | None = None
    pages: list[PageContent] = Field(default_factory=list)
    pages_needing_ocr: list[int] = Field(default_factory=list)  # 1-based
    pages_with_tables: list[int] = Field(default_factory=list)  # 1-based
    has_encoding_issues: bool = False
    is_complex_layout: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    ocr_used: bool = False  # always False until OCR is wired

    @property
    def any_scanned(self) -> bool:
        return self.pdf_type in _SCANNED_TYPES

    @property
    def scanned_pages(self) -> list[int]:
        return self.pages_needing_ocr

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages if p.text)

    def page_text(self, page_no: int) -> str:
        """Plain text of a 1-based page number ('' if unknown)."""
        if 1 <= page_no <= len(self.pages):
            return self.pages[page_no - 1].text
        return ""

    def table_lines(self, page_no: int) -> list[str]:
        """Markdown table rows (cells joined) for a page, for region attribution."""
        if 1 <= page_no <= len(self.pages):
            md = self.pages[page_no - 1].markdown
            return [
                line.strip()
                for line in md.splitlines()
                if "|" in line and "---" not in line
            ]
        return []


def extract_pdf(path: str | Path) -> Extraction:
    """Classify and extract a PDF with pdf-inspector (no OCR)."""
    p = Path(path)
    result = pdf_inspector.process_pdf(str(p))

    ext = Extraction(
        source_path=str(p),
        num_pages=int(result.page_count),
        pdf_type=result.pdf_type or "text_based",
        classification_confidence=float(result.confidence) if result.confidence is not None else None,
        pages_needing_ocr=[int(i) for i in (result.pages_needing_ocr or [])],
        pages_with_tables=[int(i) for i in (result.pages_with_tables or [])],
        has_encoding_issues=bool(result.has_encoding_issues),
        is_complex_layout=bool(result.is_complex_layout),
    )
    ext.metadata["title"] = result.title or ""
    ext.metadata["page_count"] = ext.num_pages

    # per-page markdown (PageMarkdown.page is 0-based)
    md_result = pdf_inspector.extract_pages_markdown(str(p))
    md_by_page: dict[int, str] = {
        int(pg.page) + 1: (pg.markdown or "") for pg in (md_result.pages or [])
    }

    # per-page plain text (TextItem.page is 1-based; skip image placeholders,
    # e.g. "[Image: <hash>]" that pdf-inspector emits for raster-only content)
    items = pdf_inspector.extract_text_with_positions(str(p))
    text_by_page: dict[int, list[tuple[float, float, str]]] = {}
    for item in items:
        if getattr(item, "item_type", "text") == "image":
            continue
        text_by_page.setdefault(int(item.page), []).append(
            (float(item.y), float(item.x), item.text or "")
        )

    for page_no in range(1, ext.num_pages + 1):
        rows = text_by_page.get(page_no, [])
        # sort into reading order: top-to-bottom, then left-to-right
        rows.sort(key=lambda r: (-r[0], r[1]))
        text = "\n".join(r[2] for r in rows)
        ext.pages.append(
            PageContent(
                page=page_no,
                text=text,
                markdown=md_by_page.get(page_no, ""),
                has_text=bool(text.strip()),
                needs_ocr=page_no in ext.pages_needing_ocr,
            )
        )
    return ext


def extract_text_file(path: str | Path) -> Extraction:
    """Accept a plain-text attachment directly as a single 'page'."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    ext = Extraction(source_path=str(p), num_pages=1, pdf_type="text_based")
    ext.pages.append(
        PageContent(page=1, text=text, has_text=bool(text.strip()), needs_ocr=False)
    )
    ext.metadata["title"] = p.name
    ext.metadata["page_count"] = 1
    return ext


def extract_image_file(path: str | Path) -> Extraction:
    """A bare image attachment: single image-only page (OCR still out of scope)."""
    p = Path(path)
    ext = Extraction(
        source_path=str(p),
        num_pages=1,
        pdf_type="scanned",
        pages_needing_ocr=[1],
    )
    ext.pages.append(
        PageContent(page=1, text="", has_text=False, needs_ocr=True)
    )
    ext.metadata["title"] = p.name
    ext.metadata["page_count"] = 1
    return ext


_PDF_MIMES = {"application/pdf"}
_TEXT_MIME_PREFIX = "text/"
_IMAGE_MIME_PREFIX = "image/"
_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".eml"}


def extract(path: str | Path, mime: str | None = None) -> Extraction:
    """Dispatch an attachment to the right extractor by MIME type (with suffix sniffing)."""
    p = Path(path)
    mime_l = (mime or "").lower()
    suffix = p.suffix.lower()

    if mime_l in _PDF_MIMES or suffix == ".pdf":
        return extract_pdf(p)
    if mime_l.startswith(_TEXT_MIME_PREFIX) or suffix in _TEXT_SUFFIXES:
        return extract_text_file(p)
    if mime_l.startswith(_IMAGE_MIME_PREFIX):
        return extract_image_file(p)

    raise ValueError(
        f"unsupported attachment: mime={mime!r} suffix={suffix!r} path={p}"
    )
