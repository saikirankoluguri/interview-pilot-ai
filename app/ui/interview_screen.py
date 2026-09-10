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
    microphone_state: "gr.Textbox"
    audio_state: "gr.Textbox"
    connection_state: "gr.Textbox"
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
    with gr.Row():
        microphone_state = gr.Textbox(label="Microphone state", value="Inactive", interactive=False)
        audio_state = gr.Textbox(label="Interviewer audio status", value="Idle", interactive=False)
        connection_state = gr.Textbox(
            label="Connection status", value="Disconnected", interactive=False
        )
    if realtime:
        from fastrtc import WebRTC

        microphone = WebRTC(
            label="Interview microphone",
            modality="audio",
            mode="send-receive",
            track_constraints={
                "echoCancellation": True,
                "noiseSuppression": True,
                "autoGainControl": True,
                "sampleRate": {"ideal": 16000},
                "sampleSize": {"ideal": 16},
                "channelCount": {"exact": 1},
            },
            button_labels={
                "start": "Allow microphone",
                "stop": "Disconnect microphone",
                "waiting": "Connecting...",
            },
        )
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
    gr.Markdown(
        "Microphone access is required. If permission, WebRTC, or playback fails, "
        "allow access and reconnect; use Retry audio when it is available."
    )
    retry = gr.Button("Retry interviewer audio", visible=not realtime)
    end = gr.Button("End Interview", variant="stop")
    return InterviewScreen(
        status,
        timer,
        state,
        microphone_state,
        audio_state,
        connection_state,
        microphone,
        speaker,
        end,
        retry,
    )
