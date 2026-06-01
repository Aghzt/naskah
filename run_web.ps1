# =====================================================================
#  Naskah - jalankan server web (backend FastAPI + frontend)
#  Buka http://localhost:8000 di browser setelah server siap.
# =====================================================================
param([int]$Port = 8000)

$dir = $PSScriptRoot
Set-Location $dir
$py = Join-Path $dir ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Menyalakan server Naskah di http://localhost:$Port ..." -ForegroundColor Cyan
& $py -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
