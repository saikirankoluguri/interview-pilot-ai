"""JSON sessions and reports; no database, global session dictionary, or public listing."""

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.interview.session import InterviewSession
from app.schemas.evaluation import FinalReport
from app.storage.file_store import atomic_write, contained_path
from app.utils.errors import StorageError


class SessionStore:
    def __init__(self, session_dir: Path, report_dir: Path) -> None:
        self.session_dir = session_dir.resolve()
        self.report_dir = report_dir.resolve()

    def _name(self, session_id: UUID) -> str:
        try:
            return f"{UUID(str(session_id))}.json"
        except ValueError as exc:
            raise StorageError("Invalid session identifier.") from exc

    def save(self, session: InterviewSession) -> None:
        atomic_write(
            self.session_dir,
            self._name(session.session_id),
            session.model_dump_json(indent=2).encode(),
        )

    def get(self, session_id: UUID) -> InterviewSession | None:
        path = contained_path(self.session_dir, self._name(session_id))
        try:
            session = InterviewSession.model_validate_json(path.read_text(encoding="utf-8"))
            if str(session.session_id) != str(session_id):
                raise StorageError("Session identifier mismatch.")
            return session
        except FileNotFoundError:
            return None
        except (OSError, ValidationError) as exc:
            raise StorageError("Stored session cannot be read.") from exc

    def save_report(self, report: FinalReport) -> Path:
        return atomic_write(
            self.report_dir,
            self._name(report.session_id),
            report.model_dump_json(indent=2).encode(),
        )

    def delete(self, session_id: UUID) -> None:
        for root in (self.session_dir, self.report_dir):
            try:
                contained_path(root, self._name(session_id)).unlink(missing_ok=True)
            except OSError as exc:
                raise StorageError("Could not delete interview data.") from exc
