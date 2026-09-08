"""Launch the local mock UI by default; --check validates wiring without a server."""

import argparse
import os
import warnings

from pydantic import ValidationError

from app.bootstrap import build_application
from app.config.settings import Settings
from app.utils.errors import InterviewError
from app.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="InterviewPilot AI")
    parser.add_argument("--check", action="store_true", help="Validate provider wiring and exit")
    parser.add_argument("--ui", action="store_true", help="Launch UI (the default)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    try:
        settings = Settings()
        configure_logging(settings.log_level)
        application = build_application(settings)
        print(
            f"InterviewPilot AI: {settings.app_env} / {settings.llm_provider}, "
            f"{settings.stt_provider}, {settings.tts_provider}, {settings.vad_provider}"
        )
        if not args.check:
            from app.ui.gradio_app import create_app

            with warnings.catch_warnings():
                # Gradio 5 is pinned for FastRTC 0.0.34 compatibility.
                warnings.filterwarnings(
                    "ignore",
                    message="Setting 'api_name=False'.*",
                    category=DeprecationWarning,
                )
                warnings.filterwarnings(
                    "ignore",
                    message="The 'show_api' parameter.*",
                    category=DeprecationWarning,
                )
                create_app(application).queue().launch(
                    server_name=args.host or settings.server_name,
                    server_port=args.port or settings.server_port,
                    share=False,
                    inbrowser=False,
                    show_error=False,
                    max_file_size=settings.max_upload_bytes,
                    blocked_paths=[
                        str(settings.upload_dir),
                        str(settings.transcript_dir),
                        str(settings.report_dir),
                        str(settings.recording_dir),
                    ],
                    enable_monitoring=False,
                    show_api=False,
                )
    except ValidationError:
        parser.exit(1, "Invalid configuration. Check .env provider choices and settings.\n")
    except InterviewError as exc:
        parser.exit(1, f"Cannot start InterviewPilot AI: {exc}\n")


if __name__ == "__main__":
    main()
