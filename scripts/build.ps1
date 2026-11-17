# Compila AirWin en Windows:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Interfaz (React + shadcn/ui)" -ForegroundColor Cyan
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "==> Entorno de Python" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt pyinstaller

Write-Host "==> Ejecutable" -ForegroundColor Cyan
.\.venv\Scripts\pyinstaller AirWin.spec --noconfirm

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
  Write-Host "==> Instalador" -ForegroundColor Cyan
  & $iscc installer\AirWin.iss
  Write-Host "Listo: dist\AirWin-Setup-*.exe" -ForegroundColor Green
} else {
  Write-Host "Listo: dist\AirWin\AirWin.exe  (instala Inno Setup 6 para generar el instalador)" -ForegroundColor Green
}
