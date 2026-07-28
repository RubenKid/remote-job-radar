"""Local PDF text extraction. No AI here."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def extract_text(pdf_path: str | Path) -> str:
    """Extract plain text from a PDF resume using a local parser."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"CV not found: {path}")

    parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError(
            f"No text could be extracted from {path}. "
            "Is it a scanned image PDF? OCR is not supported."
        )
    return text
