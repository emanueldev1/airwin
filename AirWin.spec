# -*- mode: python ; coding: utf-8 -*-
# Compilar con:  pyinstaller AirWin.spec --noconfirm
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# La versión sale de airwin/__init__.py (única fuente de verdad).
VERSION = re.search(r'__version__ = "([^"]+)"', Path("airwin/__init__.py").read_text("utf-8")).group(1)
nums = tuple(int(n) for n in (re.findall(r"\d+", VERSION) + ["0"] * 4)[:4])
Path("build").mkdir(exist_ok=True)
Path("build/version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', 'emanueldev1'),
      StringStruct('FileDescription', 'AirWin - AirPlay para Windows'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductName', 'AirWin'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('LegalCopyright', 'Licencia MIT')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
""", "utf-8")

datas = [("airwin/web", "airwin/web"), ("assets/icon.ico", "assets")]
binaries = []
hiddenimports = []
for pkg in ("pyatv", "soundcard", "miniaudio", "webview", "zeroconf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run_airwin.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PySide6", "PyQt5", "PyQt6", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AirWin",
    icon="assets/icon.ico",
    console=False,
    version="build/version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, name="AirWin")
