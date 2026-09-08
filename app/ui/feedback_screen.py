"""Candidate coaching is rendered only after session completion."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import gradio as gr


def build_feedback_screen() -> "gr.Markdown":
    import gradio as gr

    return gr.Markdown("Feedback will appear after the interview ends.", sanitize_html=True)
