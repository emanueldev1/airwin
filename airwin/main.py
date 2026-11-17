"""Arranque: backend asyncio + ventana nativa (pywebview / Edge WebView2)."""
from __future__ import annotations

import argparse
import logging
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from airwin import APP_NAME
from airwin.core.config import data_dir
from airwin.core.monitors import enable_dpi_awareness

log = logging.getLogger("airwin")

FILE_FILTERS = {
    "audio": ("Audio (*.mp3;*.m4a;*.aac;*.flac;*.wav;*.ogg;*.opus)", "Todos los archivos (*.*)"),
    "video": ("Video y música (*.mp4;*.m4v;*.mov;*.mkv;*.avi;*.webm;*.mp3;*.m4a)", "Todos los archivos (*.*)"),
    "exe": ("Programas (*.exe)", "Todos los archivos (*.*)"),
    "any": ("Todos los archivos (*.*)",),
}


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(data_dir() / "airwin.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    ]
    if sys.stderr:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)
    for noisy in ("pyatv", "aiohttp.access", "zeroconf"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--browser", action="store_true", help="abrir en el navegador en vez de ventana propia")
    parser.add_argument("--headless", action="store_true", help="sólo el servidor (desarrollo)")
    parser.add_argument("--port", type=int, default=47800)
    args = parser.parse_args()

    _setup_logging()
    enable_dpi_awareness()

    from airwin.core.controller import Controller
    from airwin.server import ApiServer

    ctl = Controller()
    window: dict[str, Any] = {}

    def pick_file(kind: str) -> Optional[str]:
        win = window.get("w")
        if win is None:
            return None
        import webview

        result = win.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                        file_types=FILE_FILTERS.get(kind, FILE_FILTERS["any"]))
        return result[0] if result else None

    webview_mod = None
    if not (args.browser or args.headless):
        try:
            import webview as webview_mod  # type: ignore[no-redef]
        except Exception as exc:  # noqa: BLE001
            log.warning("pywebview no disponible (%s); se usará el navegador", exc)

    stop = threading.Event()

    def quit_app() -> None:
        win = window.get("w")
        if win is not None:
            win.destroy()
        stop.set()

    server = ApiServer(ctl, pick_file if webview_mod else None, quit_app)
    ctl.runner.run_sync(server.start(args.port))
    url = server.url
    log.info("%s iniciado", APP_NAME)

    def shutdown() -> None:
        try:
            ctl.runner.run_sync(server.shutdown(), timeout=8)
        except Exception:  # noqa: BLE001
            pass
        ctl.close()

    if webview_mod is not None:
        win = webview_mod.create_window(
            APP_NAME, url, width=1180, height=760, min_size=(940, 620), background_color="#18181b",
            text_select=False,
        )
        window["w"] = win
        webview_mod.start(private_mode=False, storage_path=str(data_dir() / "webview"))
        shutdown()
        return

    if not args.headless:
        webbrowser.open(url)
    print(f"{APP_NAME} en {url}  (Ctrl+C para salir)")
    try:
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    shutdown()


if __name__ == "__main__":
    main()
