"""Rutas y configuración persistente (JSON en %APPDATA%\\AirWin)."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

from airwin import APP_NAME


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


class JsonStore:
    """Diccionario persistente sencillo y thread-safe."""

    def __init__(self, filename: str, defaults: dict[str, Any] | None = None):
        self._path = data_dir() / filename
        self._lock = threading.Lock()
        self._data: dict[str, Any] = dict(defaults or {})
        if self._path.exists():
            try:
                self._data.update(json.loads(self._path.read_text("utf-8")))
            except (OSError, ValueError):
                pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), "utf-8")
            tmp.replace(self._path)


SETTINGS = JsonStore(
    "settings.json",
    {
        "receiver_name": "AirWin PC",
        "receiver_fullscreen": False,
        "receiver_pin": "",
        "receiver_resolution": "1920x1080",
        "receiver_fps": 60,
        "receiver_audio_only": False,
        "uxplay_path": "",
        "ffmpeg_path": "",
        "media_port": 8765,
        "cast_fps": 30,
        "cast_encoder": "libx264",
        "cast_bitrate": "6M",
        "audio_latency": "low",
        "update_auto_check": True,
        "update_auto_download": True,
    },
)
CREDENTIALS = JsonStore("credentials.json")
