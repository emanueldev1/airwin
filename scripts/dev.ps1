# Desarrollo con recarga en caliente: backend + Vite en paralelo
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:AIRWIN_TOKEN = "dev"
Start-Process -NoNewWindow python -ArgumentList "-m", "airwin", "--headless"
Set-Location frontend
$env:VITE_AIRWIN_TOKEN = "dev"
npm run dev
