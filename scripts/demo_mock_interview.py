"""Deterministic developer workflow demo; no microphone, network, or model required."""

import argparse
import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Support the documented direct invocation from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bootstrap import build_application
from app.config.settings import Settings
from app.schemas.candidate import CandidateProfile
from app.schemas.interview import InterviewSettings


async def run(data_dir: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="local",
        llm_provider="mock",
        stt_provider="mock",
        tts_provider="mock",
        vad_provider="mock",
        data_dir=data_dir,
    )
    app = build_application(settings)
    candidate = CandidateProfile(
        name="Alex",
        target_role="Software Engineer",
        resume_text="Synthetic profile: built Python services and automated API tests.",
        job_description=(
            "Build reliable software services, test failure cases, and explain design trade-offs."
        ),
    )
    session = app.engine.create_session(
        candidate, InterviewSettings(target_role=candidate.target_role)
    )
    await app.engine.start_interview(session.session_id)
    for index in range(5):
        await app.engine.process_candidate_answer(
            session.session_id,
            f"Synthetic answer {index + 1}: I compared alternatives, "
            "tested failures, and measured outcomes.",
        )
        saved = app.engine.get_session(session.session_id)
        print(f"Developer trace: turn={index + 1} internal_level={saved.current_difficulty.value}")
    report = await app.engine.end_interview(session.session_id)
    print(
        f"Completed mock session: {len(report.questions)} questions, {len(saved.answers)} answers."
    )
    print("Report is a workflow fixture, not a candidate ability assessment.")
    print(f"JSON report: {settings.report_dir / str(session.session_id)}.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-data", action="store_true", help="Keep synthetic data in ignored data/demo/"
    )
    args = parser.parse_args()
    if args.keep_data:
        asyncio.run(run(Path(__file__).resolve().parents[1] / "data/cache/demo"))
    else:
        with TemporaryDirectory(prefix="interviewpilot-demo-") as directory:
            asyncio.run(run(Path(directory)))
        print("Temporary synthetic demo data removed.")


if __name__ == "__main__":
    main()
