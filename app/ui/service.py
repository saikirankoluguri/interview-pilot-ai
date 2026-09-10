"""Testable UI boundary: private session state stays server-side."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.bootstrap import Application
from app.documents.jd_parser import parse_job_description
from app.documents.resume_parser import parse_resume
from app.evaluation.report_builder import build_report, safe_text
from app.schemas.candidate import CandidateProfile
from app.schemas.interview import Difficulty, InterviewRound, InterviewSettings, SessionStatus
from app.utils.errors import InterviewError
from app.voice.audio_pipeline import AudioPipeline, VoiceResponse
from app.voice.turn_manager import ConnectionState, TurnState


@dataclass(eq=False)
class UIContext:
    """Held in gr.State only, never a component visible in the browser."""

    session_id: UUID
    voice: AudioPipeline
    feedback_shown: bool = False


class UIService:
    def __init__(self, application: Application) -> None:
        self.app = application

    async def start(
        self,
        name: str,
        role: str,
        company: str,
        resume_path: str | None,
        jd: str,
        round_name: str,
        difficulty: str,
        duration: int,
        panel_size: int,
        previous: UIContext | None = None,
    ) -> tuple[UIContext, VoiceResponse]:
        if previous is not None:
            old = self.app.engine.get_session(previous.session_id)
            if old.status not in {SessionStatus.COMPLETED, SessionStatus.FAILED}:
                raise InterviewError("End the current interview before starting another.")
        if not resume_path:
            raise InterviewError("Upload a PDF resume before starting.")
        path = Path(resume_path)
        text = parse_resume(
            path,
            max_bytes=self.app.settings.max_upload_bytes,
            max_pages=self.app.settings.max_pdf_pages,
        )
        candidate = CandidateProfile(
            name=name,
            target_role=role,
            company=company.strip() or None,
            resume_text=text,
            job_description=parse_job_description(jd),
        )
        options = InterviewSettings(
            target_role=candidate.target_role,
            company=candidate.company,
            round=InterviewRound(round_name),
            difficulty=Difficulty(difficulty),
            duration_minutes=duration,
            panel_size=panel_size,
        )
        session = self.app.engine.create_session(candidate, options)
        stored: Path | None = None
        try:
            with path.open("rb") as handle:
                stored = self.app.uploads.save(handle.read(self.app.settings.max_upload_bytes + 1))
            providers = self.app.providers
            voice = AudioPipeline(
                self.app.engine,
                session.session_id,
                providers.stt,
                providers.tts,
                providers.vad,
                self.app.settings,
            )
            if self.app.settings.realtime_transport == "gradio":
                voice.connect()
            else:
                voice.connection_state = ConnectionState.CONNECTING
            response = await voice.start()
            return UIContext(session.session_id, voice), response
        except Exception:
            # Setup failure has no live session in the browser; clean up its private artifacts.
            self.app.engine.store.delete(session.session_id)
            if stored is not None:
                self.app.uploads.delete(stored)
            raise

    def public_status(self, context: UIContext | None) -> tuple[str, str, str, str, str, str]:
        if context is None:
            return (
                "Ready for setup",
                "30:00",
                TurnState.IDLE.value,
                "Inactive",
                "Idle",
                ConnectionState.DISCONNECTED.value,
            )
        session = self.app.engine.get_session(context.session_id)
        remaining = int(session.remaining_seconds())
        panel = (
            session.panel[session.questions[-1].panel_index]
            if session.questions
            else session.panel[0]
            if session.panel
            else None
        )
        name = f"{panel.name}, {panel.title}" if panel else "Interviewer"
        status = (
            f"**{safe_text(session.candidate.name)}** | {safe_text(session.settings.target_role)} "
            f"| {session.settings.round.value} | {session.status.value}\n\n"
            f"Panel: {safe_text(name)}"
        )
        voice_state = context.voice.turns.state
        microphone = (
            "Gated"
            if voice_state == TurnState.INTERVIEWER_SPEAKING
            else "Active"
            if voice_state in {TurnState.LISTENING, TurnState.CANDIDATE_SPEAKING}
            else "Inactive"
        )
        audio = (
            "Playing"
            if voice_state == TurnState.INTERVIEWER_SPEAKING
            else "Preparing"
            if voice_state in {TurnState.PREPARING, TurnState.PROCESSING, TurnState.ENDING}
            else "Idle"
        )
        return (
            status,
            f"{remaining // 60:02d}:{remaining % 60:02d}",
            voice_state.value,
            microphone,
            audio,
            context.voice.connection_state.value,
        )

    def feedback(self, context: UIContext | None) -> str:
        if context is None:
            return "Feedback will appear after the interview ends."
        session = self.app.engine.get_session(context.session_id)
        if session.status != SessionStatus.COMPLETED or session.report is None:
            return "Feedback will appear after the interview ends."
        return build_report(session.report)
