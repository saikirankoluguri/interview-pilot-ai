"""Voice-first Gradio application with server-side private state and timer enforcement."""

import os
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.bootstrap import Application, build_application
from app.schemas.interview import SessionStatus
from app.ui.feedback_screen import build_feedback_screen
from app.ui.interview_screen import build_interview_screen
from app.ui.service import UIService
from app.ui.setup_screen import build_setup_screen
from app.utils.errors import InterviewError
from app.voice.audio_utils import from_array
from app.voice.realtime import create_realtime_transport
from app.voice.turn_manager import TurnState

if TYPE_CHECKING:
    import gradio as gr


def create_app(application: Application | None = None) -> "gr.Blocks":
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    application = application or build_application()
    os.environ["GRADIO_TEMP_DIR"] = str(application.settings.cache_dir / "gradio")
    import gradio as gr

    service = UIService(application)
    realtime = application.settings.realtime_transport == "fastrtc"
    handler = create_realtime_transport() if realtime else None

    with gr.Blocks(
        title="InterviewPilot AI", analytics_enabled=False, delete_cache=(3600, 3600)
    ) as demo:
        gr.Markdown("# InterviewPilot AI\nA focused conversation. Feedback after the interview.")
        if application.settings.llm_provider == "mock":
            gr.Markdown(
                "**Local mock demo:** audio output is short silence; "
                "transcription and scores "
                "are deterministic fixtures. This verifies the workflow, "
                "not your interview ability."
            )
        context = gr.State(None, time_to_live=7200)
        with gr.Tabs() as tabs:
            with gr.Tab("Setup", id="setup"):
                setup = build_setup_screen(application.settings)
            with gr.Tab("Interview", id="interview"):
                interview = build_interview_screen(realtime=realtime)
            with gr.Tab("Feedback", id="feedback"):
                feedback = build_feedback_screen()
        timer = gr.Timer(1, active=True)
        public_outputs = [interview.status, interview.timer, interview.voice_state]

        async def start(*values):
            try:
                state, response = await service.start(*values)
                mic_update = gr.skip() if realtime else gr.Audio(recording=True)
                return (
                    state,
                    *service.public_status(state),
                    None if realtime else response.audio.to_wav(),
                    gr.Tabs(selected="interview"),
                    "Feedback will appear after the interview ends.",
                    mic_update,
                )
            except ValidationError:
                raise gr.Error(
                    "Check the candidate details, role, and interview settings."
                ) from None
            except InterviewError as exc:
                raise gr.Error(str(exc)) from None

        start_event = setup.start.click(
            start,
            inputs=setup.inputs + [context],
            outputs=[context]
            + public_outputs
            + [interview.speaker, tabs, feedback, interview.microphone],
            api_name=False,
            concurrency_limit=1,
        )

        async def receive(state, audio):
            if state is None or audio is None:
                return gr.skip(), *service.public_status(state)
            try:
                result = await state.voice.accept_chunk(from_array(*audio))
                return result.audio.to_wav() if result else gr.skip(), *service.public_status(state)
            except InterviewError as exc:
                raise gr.Error(str(exc)) from None

        def playback_finished(state):
            if state is not None:
                state.voice.playback_finished()
            return service.public_status(state)

        if realtime:
            interview.microphone.stream(
                handler,
                inputs=[interview.microphone, context],
                outputs=[interview.microphone],
                time_limit=3700,
            )
            start_event.then(
                lambda: "start_webrtc_stream",
                outputs=interview.microphone,
                api_name=False,
            )
        else:
            interview.microphone.stream(
                receive,
                inputs=[context, interview.microphone],
                outputs=[interview.speaker] + public_outputs,
                stream_every=0.5,
                time_limit=3700,
                concurrency_limit=1,
                api_name=False,
            )
            interview.speaker.stop(
                playback_finished,
                inputs=[context],
                outputs=public_outputs,
                api_name=False,
                queue=False,
            )
            interview.speaker.pause(
                playback_finished,
                inputs=[context],
                outputs=public_outputs,
                api_name=False,
                queue=False,
            )

        async def retry(state):
            if state is None:
                raise gr.Error("Start an interview first.")
            try:
                response = await state.voice.retry_audio()
                return response.audio.to_wav(), *service.public_status(state)
            except InterviewError as exc:
                raise gr.Error(str(exc)) from None

        interview.retry.click(
            retry,
            inputs=[context],
            outputs=[interview.speaker] + public_outputs,
            api_name=False,
        )

        async def finish(state):
            if state is None:
                raise gr.Error("Start an interview first.")
            try:
                await state.voice.end()
                state.feedback_shown = True
                return (
                    *service.public_status(state),
                    service.feedback(state),
                    gr.Tabs(selected="feedback"),
                    gr.skip() if realtime else gr.Audio(recording=False),
                )
            except InterviewError as exc:
                raise gr.Error(str(exc)) from None

        interview.end.click(
            finish,
            inputs=[context],
            outputs=public_outputs + [feedback, tabs, interview.microphone],
            api_name=False,
            concurrency_limit=1,
        )

        async def tick(state):
            if state is None:
                return *service.public_status(None), gr.skip(), gr.skip(), gr.skip()
            session = application.engine.get_session(state.session_id)
            if session.status == SessionStatus.IN_PROGRESS and session.should_end():
                if state.voice.turns.state != TurnState.PROCESSING:
                    await state.voice.end()
                    session = application.engine.get_session(state.session_id)
            done = session.status == SessionStatus.COMPLETED
            switch_to_feedback = done and not state.feedback_shown
            if done:
                state.feedback_shown = True
            return (
                *service.public_status(state),
                service.feedback(state) if done else gr.skip(),
                gr.Tabs(selected="feedback") if switch_to_feedback else gr.skip(),
                gr.Audio(recording=False) if done and not realtime else gr.skip(),
            )

        timer.tick(
            tick,
            inputs=[context],
            outputs=public_outputs + [feedback, tabs, interview.microphone],
            api_name=False,
            concurrency_limit=1,
            show_progress="hidden",
        )
    return demo
