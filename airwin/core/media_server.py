"""Servidor HTTP local: el Apple TV descarga desde aquí los videos/HLS del PC."""
from __future__ import annotations

import logging
import secrets
import socket
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from aiohttp import web

log = logging.getLogger(__name__)

MIME = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def local_ip_for(target: str) -> str:
    """IP de la interfaz del PC que llega a `target` (la que debe usar el Apple TV)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 7000))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        s.close()


class MediaServer:
    def __init__(self, port: int = 8765) -> None:
        self.port = port
        self._files: dict[str, Path] = {}
        self._dirs: dict[str, Path] = {}
        self._runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        if self._runner:
            return
        app = web.Application()
        app.router.add_get("/f/{token}/{name}", self._serve_file)
        app.router.add_get("/d/{token}/{path:.+}", self._serve_dir)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        for port in (self.port, *range(self.port + 1, self.port + 20)):
            try:
                await web.TCPSite(self._runner, "0.0.0.0", port).start()
                self.port = port
                log.info("Servidor multimedia escuchando en el puerto %d", port)
                return
            except OSError:
                continue
        raise RuntimeError("No hay puertos libres para el servidor multimedia")

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    def publish_file(self, path: Path, device_address: str) -> str:
        token = secrets.token_urlsafe(8)
        self._files[token] = path
        return f"http://{local_ip_for(device_address)}:{self.port}/f/{token}/{quote(path.name)}"

    def publish_dir(self, directory: Path, entry: str, device_address: str) -> tuple[str, str]:
        token = secrets.token_urlsafe(8)
        self._dirs[token] = directory
        url = f"http://{local_ip_for(device_address)}:{self.port}/d/{token}/{quote(entry)}"
        return token, url

    def unpublish(self, token: str) -> None:
        self._files.pop(token, None)
        self._dirs.pop(token, None)

    async def _serve_file(self, request: web.Request) -> web.StreamResponse:
        path = self._files.get(request.match_info["token"])
        if not path or not path.is_file():
            raise web.HTTPNotFound()
        headers = {"Content-Type": MIME.get(path.suffix.lower(), "application/octet-stream")}
        return web.FileResponse(path, headers=headers)

    async def _serve_dir(self, request: web.Request) -> web.StreamResponse:
        base = self._dirs.get(request.match_info["token"])
        if not base:
            raise web.HTTPNotFound()
        target = (base / request.match_info["path"]).resolve()
        if base.resolve() not in target.parents or not target.is_file():
            raise web.HTTPNotFound()
        headers = {
            "Content-Type": MIME.get(target.suffix.lower(), "application/octet-stream"),
            "Cache-Control": "no-cache" if target.suffix == ".m3u8" else "max-age=60",
        }
        return web.FileResponse(target, headers=headers)
