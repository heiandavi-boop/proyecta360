$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.10 -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip setuptools wheel
& $python -m pip install -r requirements.txt

$env:Path = "C:\Program Files\nodejs;" + $env:Path
Push-Location "frontend"
npm install
npm run build
Pop-Location

$port = 8000
while (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue) {
    $port++
}

Write-Host "Iniciando Proyecta360 en http://127.0.0.1:$port"
& $python -m uvicorn app:app --reload --host 127.0.0.1 --port $port
