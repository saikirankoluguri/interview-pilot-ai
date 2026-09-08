"""Gradio candidate setup components; no candidate text-answer input."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config.settings import Settings
from app.schemas.interview import Difficulty, InterviewRound

if TYPE_CHECKING:
    import gradio as gr


@dataclass
class SetupScreen:
    inputs: list
    start: "gr.Button"


def build_setup_screen(settings: Settings) -> SetupScreen:
    import gradio as gr

    gr.Markdown(
        "## Prepare your interview\nYour resume and responses stay "
        "in this app's private runtime storage."
    )
    with gr.Row():
        name = gr.Textbox(label="Candidate name", max_lines=1)
        role = gr.Textbox(label="Target role", max_lines=1)
        company = gr.Textbox(label="Company (optional)", max_lines=1)
    resume = gr.File(label="Resume PDF", file_types=[".pdf"], type="filepath")
    jd = gr.Textbox(
        label="Job description",
        lines=5,
        placeholder="Paste the role requirements (at least 50 characters).",
    )
    with gr.Row():
        round_name = gr.Dropdown(
            [(r.value.replace("_", " ").title(), r.value) for r in InterviewRound],
            value="technical",
            label="Interview type",
        )
        difficulty = gr.Dropdown(
            [(d.value.title(), d.value) for d in Difficulty],
            value=settings.interview_default_difficulty.value,
            label="Difficulty",
        )
        duration = gr.Dropdown(
            [30, 60], value=settings.interview_default_duration_minutes, label="Duration (minutes)"
        )
        panel = gr.Dropdown([1, 2, 3], value=1, label="Panel size")
    start = gr.Button("Start Interview", variant="primary")
    return SetupScreen(
        [name, role, company, resume, jd, round_name, difficulty, duration, panel], start
    )
