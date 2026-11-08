# Starts the FitDesi API and the Flutter app.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Mobile = Join-Path $Root "mobile"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Flutter = Join-Path $Root ".tools\flutter\bin\flutter.bat"

if (-not (Test-Path $Python)) {
    throw "Python environment is missing. From backend, run: python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt"
}
if (-not (Test-Path $Flutter)) {
    throw "Flutter SDK is missing at .tools\flutter. Install Flutter or extract it there."
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
}
if (-not (Test-Path (Join-Path $Backend "fitdesi.db"))) {
    Write-Host "Seeding the food database. This runs once and takes a few minutes."
    Push-Location $Backend
    $env:PYTHONPATH = $Backend
    & $Python -m seeds.seed
    Pop-Location
}

function Test-Api {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", 8000)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Api)) {
    Start-Process powershell -WorkingDirectory $Backend -ArgumentList @(
        "-NoExit",
        "-Command",
        "& '$Python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    )
    Write-Host "Waiting for the API on http://127.0.0.1:8000"
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Api) { $ready = $true; break }
    }
    if (-not $ready) {
        throw "The API did not open port 8000. Check the FitDesi API window."
    }
}

Start-Process powershell -WorkingDirectory $Mobile -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '$Flutter' run"
)

Write-Host "FitDesi API:  http://127.0.0.1:8000/docs"
Write-Host "FitDesi Admin: http://127.0.0.1:8000/admin"
Write-Host "The phone app is starting in a second window. The emulator uses http://10.0.2.2:8000."
