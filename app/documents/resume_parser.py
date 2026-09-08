"""Local PDF extraction with size/page/text limits; no OCR or network access."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.utils.errors import DocumentParseError


def parse_resume(path: Path, *, max_bytes: int = 5 * 1024 * 1024, max_pages: int = 20) -> str:
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise DocumentParseError("Choose an existing PDF resume.")
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        if not 0 < len(raw) <= max_bytes:
            raise DocumentParseError("Resume exceeds the configured file size limit.")
        if not raw.startswith(b"%PDF-"):
            raise DocumentParseError("The uploaded file is not a PDF.")
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise DocumentParseError("Password-protected PDFs are not supported.")
        if not 1 <= len(reader.pages) <= max_pages:
            raise DocumentParseError("Resume exceeds the PDF page limit.")
        parts: list[str] = []
        for page in reader.pages:
            parts.append(" ".join((page.extract_text() or "").split()))
            if sum(map(len, parts)) > 40000:
                raise DocumentParseError("Resume contains too much text; use a shorter PDF.")
        text = " ".join(parts).strip()
        if len(text) < 30:
            raise DocumentParseError("PDF has no useful extractable text. OCR is not supported.")
        return text
    except DocumentParseError:
        raise
    except Exception as exc:
        # pypdf raises several parser-specific errors; do not expose document contents.
        raise DocumentParseError("Cannot read this PDF. Export a new text-based PDF.") from exc
