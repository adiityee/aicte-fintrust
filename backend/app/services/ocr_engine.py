"""PDF text extraction and heuristic FDR field recognition."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import fitz


FIELD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "fdr_number": (
        re.compile(r"\b(?:FDR|FD|DEPOSIT)\s*(?:NO\.?|NUMBER|#|ID)\s*[:/-]?\s*([A-Z0-9][A-Z0-9/-]{4,})", re.I),
    ),
    "ifsc": (re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", re.I),),
    "principal_amount": (
        re.compile(r"\b(?:principal|deposit|amount|sum)\s*(?:amount)?\s*[:=-]?\s*(?:INR|RS\.?|₹)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I),
    ),
    "interest_rate": (
        re.compile(r"\b(?:interest\s+)?rate\s*[:=-]?\s*([0-9]{1,2}(?:\.\d{1,2})?)\s*%", re.I),
        re.compile(r"\b([0-9]{1,2}(?:\.\d{1,2})?)\s*%\s*(?:p\.a\.?|per annum)", re.I),
    ),
    "issue_date": (
        re.compile(r"\b(?:issue|issued|deposit|opening)\s+date\s*[:=-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})", re.I),
    ),
    "maturity_date": (
        re.compile(r"\b(?:maturity|due|value)\s+date\s*[:=-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})", re.I),
    ),
    "lien_holder": (
        re.compile(r"\b(?:lien\s+(?:in\s+favo[u]?r\s+of|holder)|held\s+in\s+favo[u]?r\s+of|in\s+favo[u]?r\s+of)\s*[:=-]?\s*([^\n,;]+)", re.I),
    ),
}


def _run_ocr(page: fitz.Page) -> tuple[str, str]:
    """Use PaddleOCR when installed, then fall back to Tesseract."""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image_bytes = pixmap.tobytes("png")

    try:
        from paddleocr import PaddleOCR
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = engine.ocr(image, cls=True)
        lines = []
        for item in result or []:
            if isinstance(item, list):
                for row in item:
                    if len(row) > 1 and isinstance(row[1], (list, tuple)):
                        lines.append(str(row[1][0]))
        if lines:
            return "\n".join(lines), "paddleocr"
    except Exception:
        pass

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image), "pytesseract"
    except ImportError as exc:
        raise RuntimeError(
            "Scanned PDF needs PaddleOCR or pytesseract plus the Tesseract executable."
        ) from exc


def _find_field(field_name: str, text: str) -> dict[str, Any]:
    if field_name == "issuing_bank":
        banks = (
            ("State Bank of India", r"\b(?:SBI|STATE BANK OF INDIA)\b"),
            ("Punjab National Bank", r"\b(?:PNB|PUNJAB NATIONAL BANK)\b"),
            ("HDFC Bank", r"\bHDFC(?: BANK)?\b"),
        )
        for bank_name, pattern in banks:
            if re.search(pattern, text, re.I):
                return {"value": bank_name, "confidence": 0.96}
        return {"value": None, "confidence": 0.0}

    patterns = FIELD_PATTERNS.get(field_name, ())
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip().rstrip(".")
            confidence = 0.97 if field_name in {"ifsc", "fdr_number"} else 0.88
            return {"value": value, "confidence": confidence}
    return {"value": None, "confidence": 0.0}


def extract_fdr(pdf_path: str | Path) -> dict[str, Any]:
    """Extract readable text and common FDR fields from a PDF.

    Confidence values are heuristic indicators, not calibrated probabilities.
    """
    path = Path(pdf_path)
    with fitz.open(path) as document:
        pages = [page.get_text("text") for page in document]
        text = "\n".join(pages).strip()
        method = "pymupdf"

        if not text:
            recognized_pages: list[str] = []
            methods: list[str] = []
            for page in document:
                page_text, page_method = _run_ocr(page)
                if page_text.strip():
                    recognized_pages.append(page_text)
                    methods.append(page_method)
            text = "\n".join(recognized_pages).strip()
            method = methods[0] if methods and len(set(methods)) == 1 else "ocr"

    fields = {
        name: _find_field(name, text)
        for name in (
            "fdr_number",
            "issuing_bank",
            "ifsc",
            "principal_amount",
            "interest_rate",
            "issue_date",
            "maturity_date",
            "lien_holder",
        )
    }
    return {"source_file": path.name, "extraction_method": method, "text": text, "fields": fields}


def extract_fdr_json(pdf_path: str | Path) -> str:
    """Return :func:`extract_fdr` as JSON for callers that need a JSON string."""
    import json

    return json.dumps(extract_fdr(pdf_path), ensure_ascii=False)