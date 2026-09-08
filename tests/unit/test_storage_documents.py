"""Safe synthetic document parsing and persistence tests."""

from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.documents.jd_parser import parse_job_description
from app.documents.resume_parser import parse_resume
from app.interview.session import InterviewSession
from app.schemas.interview import InterviewSettings
from app.storage.file_store import FileStore, contained_path
from app.storage.session_store import SessionStore
from app.utils.errors import DocumentParseError, StorageError


def make_pdf(
    path: Path, text: str = "Synthetic software engineer experience in APIs and testing"
) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 40 700 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)


def test_pdf_and_jd(tmp_path):
    path = tmp_path / "resume.pdf"
    make_pdf(path)
    assert "Synthetic software" in parse_resume(path)
    with pytest.raises(DocumentParseError):
        parse_resume(path, max_bytes=10)
    with pytest.raises(DocumentParseError):
        parse_resume(tmp_path / "missing.pdf")
    unsupported = tmp_path / "resume.txt"
    unsupported.write_text("no")
    with pytest.raises(DocumentParseError):
        parse_resume(unsupported)
    path.write_bytes(b"%PDF-invalid")
    with pytest.raises(DocumentParseError):
        parse_resume(path)
    with pytest.raises(DocumentParseError):
        parse_job_description("short")
    assert "\n" not in parse_job_description("A useful job description " * 5 + "\nMore context")


@pytest.mark.parametrize(
    "name", ["../outside.pdf", "..\\outside.pdf", "C:resume.pdf", "/tmp/file", ".."]
)
def test_traversal(tmp_path, name):
    with pytest.raises(StorageError):
        contained_path(tmp_path, name)


def test_upload_generated_name(tmp_path):
    store = FileStore(tmp_path / "uploads", max_bytes=1024)
    path = store.save(b"%PDF-test")
    assert path.parent == (tmp_path / "uploads").resolve()
    with pytest.raises(StorageError):
        store.save(b"x", suffix="../test.pdf")
    with pytest.raises(StorageError):
        store.save(b"%PDF-" + b"x" * 1024)
    with pytest.raises(StorageError):
        store.delete(tmp_path / "outside.pdf")
    store.delete(path)
    assert not path.exists()


def test_session_roundtrip(tmp_path, candidate):
    store = SessionStore(tmp_path / "sessions", tmp_path / "reports")
    session = InterviewSession(
        candidate=candidate, settings=InterviewSettings(target_role=candidate.target_role)
    )
    store.save(session)
    assert store.get(session.session_id) == session
    store.save(session)
    assert not list((tmp_path / "sessions").glob("*.tmp"))
    store.delete(session.session_id)
    assert store.get(session.session_id) is None
