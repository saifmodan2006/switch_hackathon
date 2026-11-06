$ErrorActionPreference='Stop'
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
if (!(Test-Path '.venv')) { py -3.12 -m venv .venv }
& .venv\Scripts\python -m pip install -r services/api/requirements.txt
& .venv\Scripts\python scripts/init_env.py
$env:PYTHONPATH='services/api;services'
& .venv\Scripts\alembic upgrade head
npm ci --prefix apps/web
Write-Host 'Ready. Open two terminals: ./scripts/windows/start.ps1 api and ./scripts/windows/start.ps1 web'
