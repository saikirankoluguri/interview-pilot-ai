"""Render validated coaching without another unnecessary model call."""

from app.evaluation.report_builder import build_report
from app.schemas.evaluation import FinalReport


class FeedbackAgent:
    async def compose(self, report: FinalReport) -> str:
        return build_report(report)
