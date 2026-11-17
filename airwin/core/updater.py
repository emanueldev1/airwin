"""Actualizaciones automáticas desde las releases de GitHub.

Flujo: comprobar → descargar el instalador en segundo plano → verificar SHA-256
→ el usuario pulsa «Reiniciar» → instalación silenciosa de Inno Setup, que vuelve
a abrir AirWin al terminar.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

import aiohttp

from airwin import REPO, __version__
from airwin.core.config import SETTINGS, cache_dir

log = logging.getLogger(__name__)

API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL = 6 * 3600
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def parse_version(v: str) -> tuple[int, ...]:
    nums = [int(n) for n in re.findall(r"\d+", v.split("-")[0])[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def is_installed_build() -> bool:
    """True si corre desde una instalación de Inno Setup (se puede autoactualizar)."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return False
    return any(Path(sys.executable).parent.glob("unins*.exe"))


@dataclass
class UpdateState:
    status: str = "idle"  # idle | checking | uptodate | available | downloading | ready | installing | error
    current: str = __version__
    latest: Optional[str] = None
    notes: str = ""
    url: str = f"https://github.com/{REPO}/releases"
    progress: float = 0.0
    error: Optional[str] = None
    checked_at: Optional[float] = None
    can_install: bool = field(default_factory=is_installed_build)


class Updater:
    def __init__(self, on_change: Callable[[], None]) -> None:
        self.state = UpdateState()
        self._on_change = on_change
        self._asset_url: Optional[str] = None
        self._asset_name: Optional[str] = None
        self._sha256: Optional[str] = None
        self._installer: Optional[Path] = None
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    def as_dict(self) -> dict:
        return asdict(self.state)

    def _set(self, **kw) -> None:  # type: ignore[no-untyped-def]
        for k, v in kw.items():
            setattr(self.state, k, v)
        self._on_change()

    # ------------------------------------------------------------ ciclo automático
    def start_background(self) -> None:
        self._task = asyncio.ensure_future(self._loop())

    async def _loop(self) -> None:
        await asyncio.sleep(8)  # dejar que la app arranque tranquila
        while True:
            if SETTINGS.get("update_auto_check", True):
                await self.check(auto=True)
            await asyncio.sleep(CHECK_INTERVAL)

    # ------------------------------------------------------------ comprobar
    async def check(self, auto: bool = False) -> None:
        async with self._lock:
            if self.state.status in ("downloading", "installing", "ready"):
                return
            self._set(status="checking", error=None)
            try:
                headers = {"Accept": "application/vnd.github+json", "User-Agent": "AirWin-Updater"}
                timeout = aiohttp.ClientTimeout(total=20)
                async with aiohttp.ClientSession(timeout=timeout, headers=headers, trust_env=True) as s:
                    async with s.get(API_URL) as r:
                        if r.status == 404:
                            self._set(status="uptodate", checked_at=time.time())
                            return
                        r.raise_for_status()
                        rel = await r.json()
                    latest = str(rel.get("tag_name", "")).lstrip("v")
                    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
                    setup = next((n for n in assets if n.startswith("AirWin-Setup-") and n.endswith(".exe")), None)
                    self._sha256 = None
                    if "SHA256SUMS.txt" in assets:
                        async with s.get(assets["SHA256SUMS.txt"]) as r:
                            sums = await r.text()
                        for line in sums.splitlines():
                            parts = line.split()
                            if len(parts) == 2 and setup and parts[1].lstrip("*") == setup:
                                self._sha256 = parts[0].lower()
            except Exception as exc:  # noqa: BLE001
                log.warning("No se pudo comprobar si hay actualizaciones: %s", exc)
                self._set(status="error", error="Sin conexión con GitHub", checked_at=time.time())
                return

            if not latest or parse_version(latest) <= parse_version(__version__):
                self._set(status="uptodate", latest=latest or __version__, checked_at=time.time())
                return

            self._asset_name = setup
            self._asset_url = assets.get(setup) if setup else None
            self._set(status="available", latest=latest, notes=(rel.get("body") or "")[:4000],
                      url=rel.get("html_url") or self.state.url, checked_at=time.time())
            log.info("Nueva versión disponible: %s (tienes %s)", latest, __version__)

        if auto and self.state.can_install and SETTINGS.get("update_auto_download", True):
            await self.download()

    # ------------------------------------------------------------ descargar
    async def download(self) -> None:
        async with self._lock:
            if self.state.status != "available" or not self._asset_url or not self.state.can_install:
                return
            target = cache_dir() / "updates" / (self._asset_name or "AirWin-Setup.exe")
            target.parent.mkdir(parents=True, exist_ok=True)
            for old in target.parent.glob("AirWin-Setup-*.exe"):
                if old != target:
                    old.unlink(missing_ok=True)
            self._set(status="downloading", progress=0.0)
            tmp = target.with_suffix(".part")
            try:
                sha = hashlib.sha256()
                timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
                async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "AirWin-Updater"}, trust_env=True) as s:
                    async with s.get(self._asset_url) as r:
                        r.raise_for_status()
                        total = int(r.headers.get("Content-Length") or 0)
                        done = 0
                        last = 0.0
                        with open(tmp, "wb") as f:
                            async for chunk in r.content.iter_chunked(256 * 1024):
                                f.write(chunk)
                                sha.update(chunk)
                                done += len(chunk)
                                if total and time.monotonic() - last > 0.3:
                                    last = time.monotonic()
                                    self._set(progress=round(done / total, 3))
                if self._sha256 and sha.hexdigest().lower() != self._sha256:
                    raise RuntimeError("La firma SHA-256 del instalador no coincide")
                tmp.replace(target)
                self._installer = target
                self._set(status="ready", progress=1.0)
                log.info("Actualización %s descargada y verificada", self.state.latest)
            except Exception as exc:  # noqa: BLE001
                tmp.unlink(missing_ok=True)
                log.error("Falló la descarga de la actualización: %s", exc)
                self._set(status="available", error=str(exc) or "Error de descarga", progress=0.0)

    # ------------------------------------------------------------ instalar
    def install(self) -> None:
        """Lanza el instalador en modo silencioso. Quien llama debe cerrar la app enseguida."""
        if self.state.status != "ready" or not self._installer or not self._installer.exists():
            raise RuntimeError("La actualización todavía no está descargada")
        log_file = cache_dir() / "updates" / "install.log"
        args = [str(self._installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                "/CLOSEAPPLICATIONS", f"/LOG={log_file}"]
        log.info("Instalando la actualización %s", self.state.latest)
        subprocess.Popen(args, close_fds=True, creationflags=DETACHED if sys.platform == "win32" else 0)
        self._set(status="installing")
