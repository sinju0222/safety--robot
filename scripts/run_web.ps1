# Windows: from project root: powershell -ExecutionPolicy Bypass -File .\scripts\run_web.ps1 -UbuntuIP 192.168.0.25
param(
    [Parameter(Mandatory=$true)][string]$UbuntuIP,
    [Parameter(Mandatory=$true)][string]$PatrolToken,
    [ValidateSet('vlm','yolo_policy')][string]$RiskMode = 'vlm' 
)
$ErrorActionPreference = "Stop"
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $project 'backend'
$frontend = Join-Path $project 'frontend'
$ai = Join-Path $project 'ai_server'
$backendPython = Join-Path $backend '.venv\Scripts\python.exe'
if (!(Test-Path $backendPython)) { throw "backend/.venv missing: cd backend; py -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt" }
$env:SAFETY_PATROL_CONTROLLER_URL = "http://${UbuntuIP}:8090"
$env:SAFETY_PATROL_TOKEN = $PatrolToken
$env:SAFETY_RISK_MODE = $RiskMode
$env:SAFETY_AI_SERVER_URL = 'http://127.0.0.1:8001'
Start-Process powershell -ArgumentList @('-NoExit','-Command',"Set-Location '$backend'; `$env:SAFETY_PATROL_CONTROLLER_URL='$env:SAFETY_PATROL_CONTROLLER_URL'; `$env:SAFETY_PATROL_TOKEN='$env:SAFETY_PATROL_TOKEN'; `$env:SAFETY_RISK_MODE='$env:SAFETY_RISK_MODE'; `$env:SAFETY_AI_SERVER_URL='http://127.0.0.1:8001'; & '$backendPython' -m uvicorn main:app --host 0.0.0.0 --port 8000")
if ($RiskMode -eq 'vlm' -and (Test-Path (Join-Path $ai '.env'))) {
    $aiPython = Join-Path $ai '.venv\Scripts\python.exe'
    if (Test-Path $aiPython) {
        Start-Process powershell -ArgumentList @('-NoExit','-Command',"Set-Location '$ai'; & '$aiPython' -m uvicorn main:app --host 127.0.0.1 --port 8001")
    } else { Write-Warning "AI server .env exists but ai_server/.venv is missing; see README." }
} elseif ($RiskMode -eq 'vlm') { Write-Warning "VLM selected but ai_server/.env missing; VLM risk assessment will report errors." }
Start-Process powershell -ArgumentList @('-NoExit','-Command',"Set-Location '$frontend'; npm run dev -- --host 127.0.0.1")
Write-Host 'Backend, frontend (and AI if configured) launch windows opened. Do not close them.'
