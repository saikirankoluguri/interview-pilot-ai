"""Voice-focused interview components; no transcript, scores, or answer textbox."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import gradio as gr


@dataclass
class InterviewScreen:
    status: "gr.Markdown"
    timer: "gr.Textbox"
    voice_state: "gr.Textbox"
    microphone: object
    speaker: "gr.Audio"
    end: "gr.Button"
    retry: "gr.Button"


def build_interview_screen(*, realtime: bool = False) -> InterviewScreen:
    import gradio as gr

    gr.Markdown(
        "## Live interview\nAllow microphone access and keep speaking naturally. "
        "Answers are sent automatically. Use headphones to reduce echo."
    )
    status = gr.Markdown("Ready for setup")
    with gr.Row():
        timer = gr.Textbox(label="Time remaining", value="30:00", interactive=False)
        state = gr.Textbox(label="Voice state", value="Waiting", interactive=False)
    if realtime:
        from fastrtc import WebRTC

        microphone = WebRTC(label="Interview microphone", modality="audio", mode="send-receive")
    else:
        microphone = gr.Audio(
            label="Microphone", sources=["microphone"], type="numpy", streaming=True
        )
    speaker = gr.Audio(
        label="Interviewer audio",
        interactive=False,
        autoplay=True,
        format="wav",
        visible=not realtime,
    )
    gr.Markdown("If your browser blocks autoplay, press play on the interviewer audio.")
    retry = gr.Button("Retry interviewer audio", visible=not realtime)
    end = gr.Button("End Interview", variant="stop")
    return InterviewScreen(status, timer, state, microphone, speaker, end, retry)
