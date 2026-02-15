$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$HOLDINGS_PROVIDER = 'mock'
$QUOTE_PROVIDER = 'mock'
$INDEX_PROVIDER = 'mock'
$GOLD_PROVIDER = 'mock'

Write-Host '[1/4] Check/Create virtual environment (.venv) ...'
if (-not (Test-Path '.venv')) {
  python -m venv .venv
}

Write-Host '[2/4] Activate virtual environment ...'
. .\.venv\Scripts\Activate.ps1

Write-Host '[3/4] Install dependencies ...'
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  Write-Error 'pip install failed'
  exit 1
}

Write-Host '[4/4] Start FastAPI (uvicorn) ...'
$env:HOLDINGS_PROVIDER = $HOLDINGS_PROVIDER
$env:QUOTE_PROVIDER = $QUOTE_PROVIDER
$env:INDEX_PROVIDER = $INDEX_PROVIDER
$env:GOLD_PROVIDER = $GOLD_PROVIDER
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
