"""Transmisión de pantalla / conversión de video a HLS con ffmpeg.

El Apple TV no acepta duplicación de pantalla de terceros (FairPlay), pero sí
reproduce cualquier stream HLS por AirPlay. Capturamos el escritorio con ffmpeg,
lo servimos como HLS y se lo pasamos al Apple TV con play_url. Latencia: ~3-8 s.
"""
from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from airwin.core.config import SETTINGS, cache_dir

log = logging.getLogger(__name__)

DIRECT_PLAY_EXT = {".mp4", ".m4v", ".mov", ".mp3", ".m4a", ".aac", ".wav"}
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

ENCODERS = {
    "libx264": "Procesador (x264)",
    "h264_nvenc": "NVIDIA NVENC",
    "h264_qsv": "Intel Quick Sync",
    "h264_amf": "AMD AMF",
}


def find_ffmpeg() -> Optional[str]:
    custom = SETTINGS.get("ffmpeg_path")
    if custom and Path(custom).is_file():
        return custom
    found = shutil.which("ffmpeg")
    if found:
        return found
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        patterns = [
            os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe"),
            os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
        ]
        for pat in patterns:
            hits = glob.glob(pat)
            if hits:
                return hits[0]
    return None


def _encoder_args(encoder: str, fps: int, bitrate: str) -> list[str]:
    common = ["-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate,
              "-g", str(fps), "-keyint_min", str(fps), "-pix_fmt", "yuv420p"]
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p3", "-tune", "ll", "-forced-idr", "1", *common]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "veryfast", *common]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-usage", "lowlatency", *common]
    return ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-profile:v", "high", "-sc_threshold", "0", *common]


class HlsJob:
    """Un proceso ffmpeg que genera un stream HLS en una carpeta temporal."""

    def __init__(self, name: str) -> None:
        self.dir = cache_dir() / "hls" / f"{name}-{int(time.time())}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.playlist = self.dir / "index.m3u8"
        self.proc: Optional[subprocess.Popen] = None
        self._audio_sink = None
        self.last_error = ""

    # ---- constructores ----
    def start_screen(self, rect: tuple[int, int, int, int], fps: int, encoder: str,
                     bitrate: str, audio_hub=None) -> None:  # type: ignore[no-untyped-def]
        x, y, w, h = rect
        w -= w % 2
        h -= h % 2
        inputs = ["-f", "gdigrab", "-framerate", str(fps), "-offset_x", str(x), "-offset_y", str(y),
                  "-video_size", f"{w}x{h}", "-draw_mouse", "1", "-i", "desktop"]
        if sys.platform != "win32":  # sólo para pruebas en Linux
            inputs = ["-f", "x11grab", "-framerate", str(fps), "-video_size", f"{w}x{h}",
                      "-i", f"{os.environ.get('DISPLAY', ':0')}+{x},{y}"]
        audio_in: list[str] = []
        audio_out = ["-an"]
        if audio_hub is not None:
            audio_in = ["-use_wallclock_as_timestamps", "1", "-f", "s16le", "-ar", "44100",
                        "-ac", "2", "-i", "pipe:0"]
            audio_out = ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k",
                         "-af", "aresample=async=1"]
        args = [
            "-hide_banner", "-loglevel", "warning", "-thread_queue_size", "512", *inputs,
            *(["-thread_queue_size", "512"] if audio_in else []), *audio_in,
            "-vf", "scale='min(1920,iw)':-2", *_encoder_args(encoder, fps, bitrate), *audio_out,
            "-f", "hls", "-hls_time", "1", "-hls_list_size", "4",
            "-hls_flags", "delete_segments+independent_segments+omit_endlist",
            "-hls_segment_filename", str(self.dir / "seg_%05d.ts"), str(self.playlist),
        ]
        self._spawn(args, stdin=subprocess.PIPE if audio_hub is not None else None)
        if audio_hub is not None:
            from airwin.core.live_audio import PacedPipeSink

            self._audio_sink = PacedPipeSink(audio_hub, self.proc.stdin)

    def start_transcode(self, source: str, encoder: str, bitrate: str = "8M") -> None:
        args = [
            "-hide_banner", "-loglevel", "warning", "-i", source,
            "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale='min(1920,iw)':-2",
            *_encoder_args(encoder, 30, bitrate),
            "-c:a", "aac", "-b:a", "192k", "-ac", "2",
            "-f", "hls", "-hls_time", "4", "-hls_list_size", "0", "-hls_playlist_type", "event",
            "-hls_segment_filename", str(self.dir / "seg_%05d.ts"), str(self.playlist),
        ]
        self._spawn(args)

    # ---- ciclo de vida ----
    def _spawn(self, args: list[str], stdin=None) -> None:  # type: ignore[no-untyped-def]
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("No se encontró ffmpeg. Instálalo desde Configuración → Componentes "
                               "o indica su ruta allí.")
        cmd = [ffmpeg, *args]
        log.debug("ffmpeg: %s", " ".join(cmd))
        self.proc = subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                     creationflags=CREATE_NO_WINDOW)
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.last_error = line
                log.info("ffmpeg: %s", line)

    def wait_ready(self, min_segments: int = 2, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"ffmpeg terminó inesperadamente: {self.last_error}")
            if self.playlist.exists():
                text = self.playlist.read_text("utf-8", "ignore")
                if text.count("#EXTINF") >= min_segments:
                    return
            time.sleep(0.25)
        raise RuntimeError("ffmpeg tarda demasiado en generar el video")

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self._audio_sink is not None:
            self._audio_sink.close()
            self._audio_sink = None
        if self.proc and self.proc.poll() is None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
            except OSError:
                pass
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.dir, ignore_errors=True)


def cleanup_old_hls() -> None:
    shutil.rmtree(cache_dir() / "hls", ignore_errors=True)
