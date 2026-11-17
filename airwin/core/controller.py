"""Lógica de la app, independiente de la interfaz (todo corre en el bucle asyncio)."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from pyatv.const import Protocol
from pyatv.interface import MediaMetadata

from airwin.core import live_audio
from airwin.core.async_runner import AsyncRunner
from airwin.core.casting import DIRECT_PLAY_EXT, HlsJob, cleanup_old_hls
from airwin.core.config import SETTINGS
from airwin.core.devices import DeviceManager
from airwin.core.media_server import MediaServer

log = logging.getLogger(__name__)


class Controller:
    def __init__(self) -> None:
        self.runner = AsyncRunner()
        self.devices = DeviceManager(self.runner.loop)
        self.media = MediaServer(int(SETTINGS.get("media_port") or 8765))
        self.audio_hub = live_audio.SystemAudioHub()
        self.audio_tasks: dict[str, asyncio.Task] = {}
        self.video_tasks: dict[str, asyncio.Task] = {}
        self.hls_jobs: dict[str, HlsJob] = {}
        self.on_stream_state: Optional[Callable[[], None]] = None
        cleanup_old_hls()

    # ------------------------------------------------------------- audio
    async def stream_audio(self, idents: list[str], file: Optional[str]) -> None:
        """Envía el sonido del PC (file=None) o un archivo a uno o varios altavoces."""
        for ident in idents:
            await self.stop_audio(ident)
            atv = await self.devices.connect(ident)
            name = self.devices.devices[ident].name
            if file is None:
                source = self.audio_hub.subscribe()
                meta = MediaMetadata(title="Sonido del PC", artist="AirWin")
            else:
                source, meta = file, None
            task = asyncio.ensure_future(atv.stream.stream_file(source, metadata=meta))
            self.audio_tasks[ident] = task
            task.add_done_callback(lambda t, i=ident, n=name: self._audio_done(i, n, t))
            log.info("Transmitiendo %s a %s", "sonido del PC" if file is None else Path(file).name, name)
        self._notify()

    def _audio_done(self, ident: str, name: str, task: asyncio.Task) -> None:
        if self.audio_tasks.get(ident) is task:
            self.audio_tasks.pop(ident, None)
        if not task.cancelled() and task.exception():
            log.error("La transmisión a %s falló: %s", name, task.exception())
        else:
            log.info("Transmisión a %s terminada", name)
        self._notify()

    async def stop_audio(self, ident: Optional[str] = None) -> None:
        targets = [ident] if ident else list(self.audio_tasks)
        for i in targets:
            task = self.audio_tasks.pop(i, None)
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self._notify()

    async def set_volume(self, ident: str, level: float) -> None:
        atv = await self.devices.connect(ident)
        await atv.audio.set_volume(max(0.0, min(100.0, level)))

    async def get_volume(self, ident: str) -> float:
        atv = await self.devices.connect(ident)
        try:
            return float(atv.audio.volume)
        except Exception:  # noqa: BLE001
            return 50.0

    # ------------------------------------------------------------- video
    async def play_url(self, ident: str, url: str) -> None:
        await self.stop_video(ident)
        atv = await self.devices.connect(ident)
        log.info("Reproduciendo en %s: %s", self.devices.devices[ident].name, url)
        task = asyncio.ensure_future(atv.stream.play_url(url))
        self.video_tasks[ident] = task
        task.add_done_callback(lambda t: self._video_done(ident, t))
        self._notify()

    async def play_file(self, ident: str, path: str, force_convert: bool = False) -> None:
        await self.media.start()
        dev = self.devices.devices[ident]
        p = Path(path)
        if p.suffix.lower() in DIRECT_PLAY_EXT and not force_convert:
            url = self.media.publish_file(p, dev.address)
        else:
            job = HlsJob("video")
            job.start_transcode(str(p), SETTINGS.get("cast_encoder") or "libx264")
            await asyncio.get_running_loop().run_in_executor(None, job.wait_ready, 2, 60)
            self.hls_jobs[ident] = job
            _, url = self.media.publish_dir(job.dir, "index.m3u8", dev.address)
        await self.play_url(ident, url)

    async def cast_screen(self, ident: str, rect: tuple[int, int, int, int], with_audio: bool) -> None:
        await self.stop_video(ident)
        await self.media.start()
        dev = self.devices.devices[ident]
        job = HlsJob("screen")
        job.start_screen(
            rect,
            int(SETTINGS.get("cast_fps") or 30),
            SETTINGS.get("cast_encoder") or "libx264",
            SETTINGS.get("cast_bitrate") or "6M",
            audio_hub=self.audio_hub if with_audio else None,
        )
        try:
            await asyncio.get_running_loop().run_in_executor(None, job.wait_ready, 2, 30)
        except Exception:
            job.stop()
            raise
        self.hls_jobs[ident] = job
        _, url = self.media.publish_dir(job.dir, "index.m3u8", dev.address)
        await self.play_url(ident, url)

    def _video_done(self, ident: str, task: asyncio.Task) -> None:
        if self.video_tasks.get(ident) is task:
            self.video_tasks.pop(ident, None)
            job = self.hls_jobs.pop(ident, None)
            if job:
                job.stop()
        if not task.cancelled() and task.exception():
            log.error("Reproducción en el dispositivo falló: %s", task.exception())
        else:
            log.info("Reproducción terminada")
        self._notify()

    async def stop_video(self, ident: Optional[str] = None) -> None:
        targets = [ident] if ident else list(set(self.video_tasks) | set(self.hls_jobs))
        for i in targets:
            task = self.video_tasks.pop(i, None)
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                try:
                    atv = await self.devices.connect(i)
                    await atv.remote_control.stop()
                except Exception:  # noqa: BLE001
                    pass
            job = self.hls_jobs.pop(i, None)
            if job:
                job.stop()
        self._notify()

    # ------------------------------------------------------------- mando
    async def remote(self, ident: str, action: str) -> None:
        atv = await self.devices.connect(ident)
        if action in ("turn_on", "turn_off"):
            await getattr(atv.power, action)()
        elif action in ("volume_up", "volume_down"):
            await getattr(atv.audio, action)()
        else:
            await getattr(atv.remote_control, action)()

    async def list_apps(self, ident: str) -> list[tuple[str, str]]:
        atv = await self.devices.connect(ident)
        apps = await atv.apps.app_list()
        return sorted(((a.name or a.identifier, a.identifier) for a in apps), key=lambda x: x[0].lower())

    async def launch_app(self, ident: str, bundle_id: str) -> None:
        atv = await self.devices.connect(ident)
        await atv.apps.launch_app(bundle_id)

    async def send_text(self, ident: str, text: str) -> None:
        atv = await self.devices.connect(ident)
        await atv.keyboard.text_set(text)

    # ------------------------------------------------------------- general
    def _notify(self) -> None:
        if self.on_stream_state:
            self.on_stream_state()

    async def shutdown(self) -> None:
        await self.stop_audio()
        await self.stop_video()
        await self.devices.disconnect_all()
        await self.media.stop()

    def close(self) -> None:
        try:
            self.runner.run_sync(self.shutdown(), timeout=8)
        except Exception:  # noqa: BLE001
            log.exception("Error al cerrar")
        self.runner.stop()


PAIRABLE = [Protocol.AirPlay, Protocol.Companion, Protocol.RAOP, Protocol.MRP]
