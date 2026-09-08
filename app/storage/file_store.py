"""Bounded uploads and atomic private storage under explicitly configured roots."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from app.utils.errors import StorageError


def contained_path(root: Path, name: str) -> Path:
    """Reject traversal, Windows drive syntax, symlinks outside root, and subpaths."""
    if not name or name in {".", ".."} or any(c in name for c in "/\\:"):
        raise StorageError("Unsafe storage filename.")
    root = root.resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise StorageError("Storage path escapes its configured directory.")
    return path


def atomic_write(root: Path, name: str, content: bytes) -> Path:
    """Flush a temporary sibling before atomic replacement; never partially write JSON."""
    path = contained_path(root, name)
    temporary: Path | None = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=root, prefix=".write-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise StorageError("Could not save private interview data.") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


class FileStore:
    """Save validated resume bytes under generated UUID names, never upload names."""

    def __init__(self, root: Path, max_bytes: int = 5 * 1024 * 1024) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def save(self, content: bytes, *, suffix: str = ".pdf") -> Path:
        if suffix.lower() != ".pdf" or not content.startswith(b"%PDF-"):
            raise StorageError("Only PDF resume uploads are supported.")
        if not 0 < len(content) <= self.max_bytes:
            raise StorageError("Resume exceeds the upload size limit.")
        return atomic_write(self.root, f"{uuid4()}.pdf", content)

    def delete(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved.parent != self.root or resolved.suffix.lower() != ".pdf":
            raise StorageError("Cannot delete a file outside the upload store.")
        try:
            resolved.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Could not delete the uploaded resume.") from exc
