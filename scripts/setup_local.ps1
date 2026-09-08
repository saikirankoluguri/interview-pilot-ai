# Lightweight local setup only. Run explicitly from PowerShell.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonCommand = Get-Command python -ErrorAction Stop
    & $pythonCommand.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
    if (-not (Test-Path -LiteralPath '.venv')) {
        & $pythonCommand.Source -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    $venvPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Invalid .venv: Python missing.' }
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    & $venvPython -m pip install -r requirements-base.txt
    if ($LASTEXITCODE -ne 0) { throw 'Base dependency installation failed.' }
    Write-Host 'GPU/AI model dependencies are NOT installed by this script.'
    Write-Host 'Local environment ready. Copy .env.example to .env if needed.'
    Write-Host 'Run: ./.venv/Scripts/python.exe -m app.main'
} finally {
    Pop-Location
}
