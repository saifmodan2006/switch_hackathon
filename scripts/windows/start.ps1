param([ValidateSet('api','web','agents','worker')][string]$Service='api')
$ErrorActionPreference='Stop'
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$env:PYTHONPATH="services/api;services"
switch ($Service) {
  'api' { & .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }
  'web' { npm run dev --prefix apps/web }
  'agents' { & .venv\Scripts\python -m agents.runtime.engine }
  'worker' { & .venv\Scripts\arq app.workers.jobs.WorkerSettings }
}
