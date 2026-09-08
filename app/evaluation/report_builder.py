"""Readable post-interview report; escape candidate text before Markdown rendering."""

import html

from app.schemas.evaluation import FinalReport


def safe_text(text: str) -> str:
    """Prevent raw HTML, links, and image embeds in candidate/provider content."""
    result = html.escape(text)
    for character in "\\`*_{}[]()#+-.!|>":
        result = result.replace(character, "\\" + character)
    return result


def build_report(report: FinalReport) -> str:
    lines = ["# Interview feedback"]
    if report.is_mock:
        lines.append("**MOCK REPORT: workflow demonstration, not an ability assessment.**")
    lines += [
        f"Overall: **{report.overall_score:.1f}/100**",
        "",
        "| Category | Score |",
        "| --- | --- |",
    ]
    for label, value in [
        ("Technical", report.technical_score),
        ("Relevance", report.relevance_score),
        ("Depth", report.depth_score),
        ("Practical evidence", report.practical_experience_score),
        ("Communication", report.communication_score),
    ]:
        lines.append(f"| {label} | {value:.1f} |")
    for title, entries in [
        ("Strengths", report.strengths),
        ("Areas to improve", report.weaknesses),
    ]:
        lines.extend(["", f"## {title}", ""] + [f"- {safe_text(v)}" for v in entries])
    for index, item in enumerate(report.questions, 1):
        lines += [
            "",
            f"## Question {index}",
            "",
            safe_text(item.question),
            "",
            f"Score: {item.score:.1f}/100",
            "",
            "**Your transcript**",
            "",
            safe_text(item.answer_transcript),
            "",
            "**What went well**",
            "",
        ]
        lines += [f"- {safe_text(v)}" for v in item.done_well]
        lines += ["", "**Missing points**", ""] + [f"- {safe_text(v)}" for v in item.missing]
        lines += [
            "",
            "**Expected concepts**",
            "",
            safe_text(item.interviewer_expected),
            "",
            "**Better / ideal answer**",
            "",
            safe_text(item.ideal_answer),
            "",
            "**Review topics:** " + ", ".join(safe_text(v) for v in item.recommended_topics),
        ]
    lines += ["", "## Preparation", ""]
    lines += [f"- {safe_text(v)}" for v in report.weak_topics + report.preparation_recommendations]
    lines += ["", "**Next mock focus:** " + safe_text(report.next_mock_focus)]
    return "\n".join(lines)
