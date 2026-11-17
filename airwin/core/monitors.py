"""Lista de monitores con coordenadas físicas (las que usa ffmpeg gdigrab)."""
from __future__ import annotations

import sys
from typing import Any


def list_monitors() -> list[dict[str, Any]]:
    if sys.platform == "win32":
        try:
            return _win_monitors()
        except Exception:  # noqa: BLE001
            pass
    return [{"name": "Pantalla principal", "rect": [0, 0, 1920, 1080], "primary": True}]


def _win_monitors() -> list[dict[str, Any]]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    monitors: list[dict[str, Any]] = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )

    def callback(hmon, _hdc, _rect, _data):  # type: ignore[no-untyped-def]
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        r = info.rcMonitor
        idx = len(monitors) + 1
        primary = bool(info.dwFlags & 1)
        monitors.append({
            "name": f"Pantalla {idx}{' (principal)' if primary else ''}",
            "rect": [r.left, r.top, r.right - r.left, r.bottom - r.top],
            "primary": primary,
        })
        return 1

    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    monitors.sort(key=lambda m: not m["primary"])
    return monitors


def enable_dpi_awareness() -> None:
    """Coordenadas en píxeles reales aunque Windows tenga escalado (125%, 150%…)."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass
