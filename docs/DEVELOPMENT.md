# Development

The local mock application is implemented for Python 3.11-3.13. Run every command
from the repository root. Do not create a nested project directory.

## Setup and run

```powershell
./scripts/setup_local.ps1
# Optional local override; safe defaults work without this file:
Copy-Item .env.example .env
./.venv/Scripts/python.exe -m app.main
```

`setup_local.ps1` is idempotent, installs only `requirements-base.txt`, and prints
that GPU/AI model dependencies are not installed. It never runs cloud scripts or
downloads weights. The UI binds to loopback unless explicitly configured.

```powershell
./.venv/Scripts/python.exe -m app.main --check
./.venv/Scripts/python.exe scripts/demo_mock_interview.py
./.venv/Scripts/python.exe -m pytest -p no:cacheprovider
./.venv/Scripts/ruff.exe check .
./.venv/Scripts/ruff.exe format --check .
```

Tests disable analytics, set Hugging Face offline mode, and block external socket
connections. Cloud adapters are exercised with mocked HTTP and fake runtime
modules. The demo uses temporary synthetic storage unless `--keep-data` is given.

## Dependency compatibility

Base dependencies contain no AI model runtime. Gradio is constrained to
`>=5.49,<6` because FastRTC 0.0.34 requires Gradio below 6. The deprecated
`api_name=False` callback option is intentionally used for private callbacks in
this supported Gradio range; upgrade it to `api_visibility="private"` only when a
FastRTC release supporting Gradio 6 is selected and the UI is retested.

GPU dependencies are isolated in `requirements-gpu.txt` and must never be
installed on the local laptop. Do not run `scripts/setup_lightning.sh` or
`scripts/download_models.sh` locally.

## Design rules

Keep provider selection in `app/providers/factory.py` and composition in
`app/bootstrap.py`. Keep candidate content out of logs. Live UI outputs may not
include transcripts, scores, rationale, missing concepts, coaching, or ideal
answers. Stubs are intentional only for the future Research Agent and deployment
scaffolds. Use synthetic fixtures and validate all provider output with schemas.

## Private GitHub repository

Review all untracked files before the first commit. Because this repository may
have been initialized by a sandbox account, use a command-scoped safe-directory
setting rather than changing global Git trust:

```powershell
$repoRoot = (Get-Location).Path.Replace('\', '/')
git -c safe.directory="$repoRoot" status --short
git -c safe.directory="$repoRoot" add .
git -c safe.directory="$repoRoot" diff --cached --stat
git -c safe.directory="$repoRoot" diff --cached
git -c safe.directory="$repoRoot" commit -m "feat: complete local InterviewPilot AI application foundation"
git -c safe.directory="$repoRoot" branch -M main
git -c safe.directory="$repoRoot" remote add origin https://github.com/YOUR_GITHUB_USERNAME/interview-pilot-ai.git
git -c safe.directory="$repoRoot" remote -v
git -c safe.directory="$repoRoot" push -u origin main
```

Create an empty **private** GitHub repository first. These commands are guidance;
no commit, remote creation, or push is performed automatically.