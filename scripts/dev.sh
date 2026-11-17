#!/usr/bin/env bash
# Desarrollo en Linux/macOS (sin captura WASAPI ni gdigrab, pero útil para la interfaz)
cd "$(dirname "$0")/.."
AIRWIN_TOKEN=dev python3 -m airwin --headless &
trap "kill $!" EXIT
cd frontend && VITE_AIRWIN_TOKEN=dev npm run dev
