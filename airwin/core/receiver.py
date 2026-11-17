"""Receptor AirPlay (el PC aparece como si fuera un Apple TV) usando UxPlay."""
from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from airwin.core.config import SETTINGS

log = logging.getLogger(__name__)
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def find_uxplay() -> Optional[str]:
    custom = SETTINGS.get("uxplay_path")
    if custom and Path(custom).is_file():
        return custom
    found = shutil.which("uxplay")
    if found:
        return found
    if sys.platform == "win32":
        roots = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"),
            r"C:\msys64\ucrt64\bin",
            r"C:\msys64\mingw64\bin",
        ]
        for root in roots:
            for pat in ("uxplay*\\**\\uxplay.exe", "UxPlay*\\**\\uxplay.exe", "leapbtw*\\**\\uxplay.exe", "uxplay.exe"):
                hits = glob.glob(os.path.join(root, pat), recursive=True)
                if hits:
                    return hits[0]
    return None


def find_bonjour() -> Optional[str]:
    """UxPlay en Windows necesita el servicio Bonjour de Apple (mDNS)."""
    if sys.platform != "win32":
        return "avahi/mdns del sistema"
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")):
        if root:
            p = Path(root) / "Bonjour" / "mDNSResponder.exe"
            if p.is_file():
                return str(p)
    try:
        out = subprocess.run(["sc", "query", "Bonjour Service"], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW, timeout=5)
        if "RUNNING" in out.stdout or "STOPPED" in out.stdout:
            return "Bonjour Service"
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class AirPlayReceiver:
    def __init__(self, on_line: Callable[[str], None], on_exit: Callable[[int], None]) -> None:
        self._on_line = on_line
        self._on_exit = on_exit
        self.proc: Optional[subprocess.Popen] = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def build_args(self) -> list[str]:
        args = ["-n", SETTINGS.get("receiver_name") or "AirWin PC", "-nh"]
        res = SETTINGS.get("receiver_resolution")
        if res:
            args += ["-s", res]
        fps = SETTINGS.get("receiver_fps")
        if fps:
            args += ["-fps", str(fps)]
        if SETTINGS.get("receiver_fullscreen"):
            args.append("-fs")
        if SETTINGS.get("receiver_audio_only"):
            args += ["-vs", "0"]
        pin = (SETTINGS.get("receiver_pin") or "").strip()
        if pin:
            args += ["-pin", pin] if pin.isdigit() and len(pin) == 4 else ["-pin"]
        # Puertos fijos -> se pueden abrir en el firewall de Windows.
        args += ["-p"]
        return args

    def start(self) -> None:
        if self.running:
            return
        exe = find_uxplay()
        if not exe:
            raise RuntimeError(
                "No se encontró UxPlay. Instálalo desde Configuración → Componentes "
                "(o con 'winget install leapbtw.uxplay')."
            )
        cmd = [exe, *self.build_args()]
        log.info("Iniciando receptor: %s", " ".join(cmd))
        env = dict(os.environ)
        # GStreamer suele venir junto a uxplay.exe en el build de Windows.
        exe_dir = str(Path(exe).parent)
        env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")
        self.proc = subprocess.Popen(
            cmd, cwd=exe_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        proc = self.proc
        assert proc and proc.stdout
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self._on_line(line)
        self._on_exit(proc.wait())

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
