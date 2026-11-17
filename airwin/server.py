"""API HTTP local + eventos en tiempo real (SSE) para la interfaz web.

Sólo escucha en 127.0.0.1 y exige un token aleatorio por sesión, así ninguna
otra web abierta en el navegador puede controlar tus dispositivos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from aiohttp import web
from pyatv.const import Protocol

from airwin import APP_NAME, __version__
from airwin.core.casting import ENCODERS, find_ffmpeg
from airwin.core.config import SETTINGS
from airwin.core.controller import Controller
from airwin.core.devices import PROTOCOL_LABELS, Device
from airwin.core.monitors import list_monitors
from airwin.core.updater import Updater
from airwin.core.receiver import AirPlayReceiver, find_bonjour, find_uxplay

log = logging.getLogger(__name__)

WEB_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "airwin" / "web"
if not WEB_DIR.exists():
    WEB_DIR = Path(__file__).resolve().parent / "web"

WINGET_IDS = {"uxplay": "leapbtw.uxplay", "ffmpeg": "Gyan.FFmpeg", "bonjour": "Apple.Bonjour"}

SETTING_KEYS = {
    "receiver_name", "receiver_fullscreen", "receiver_pin", "receiver_resolution", "receiver_fps",
    "receiver_audio_only", "uxplay_path", "ffmpeg_path", "media_port", "cast_fps", "cast_encoder",
    "cast_bitrate", "theme", "update_auto_check", "update_auto_download",
}


def _device_json(d: Device) -> dict[str, Any]:
    from airwin.core.config import CREDENTIALS

    stored = CREDENTIALS.get(d.identifier, {}) or {}
    return {
        "id": d.identifier,
        "name": d.name,
        "address": d.address,
        "model": d.model,
        "kind": d.kind,
        "protocols": [p.name for p in d.protocols],
        "needsPairing": [p.name for p in d.needs_pairing()],
        "paired": list(stored.keys()),
        "pairable": [{"id": p.name, "label": PROTOCOL_LABELS[p]} for p in d.pairable_protocols()],
        "hasScreen": d.has_screen,
        "canAudio": d.can_stream_audio,
        "canVideo": Protocol.AirPlay in d.protocols and d.has_screen,
        "canRemote": d.can_remote,
    }


class ApiServer:
    def __init__(
        self,
        ctl: Controller,
        pick_file: Optional[Callable[[str], Optional[str]]] = None,
        quit_app: Optional[Callable[[], None]] = None,
    ) -> None:
        self.ctl = ctl
        self.pick_file = pick_file
        self.quit_app = quit_app
        self.token = os.environ.get("AIRWIN_TOKEN") or secrets.token_urlsafe(24)
        self.port = 0
        self.loop = ctl.runner.loop
        self._clients: set[asyncio.Queue] = set()
        self._pairing: dict[str, tuple[str, Any]] = {}
        self._scanning = False
        self._installing: set[str] = set()
        self._level_task: Optional[asyncio.Task] = None
        self.receiver = AirPlayReceiver(
            on_line=lambda line: self.emit_threadsafe({"type": "receiver", "line": line}),
            on_exit=lambda code: self.loop.call_soon_threadsafe(self._receiver_exited, code),
        )
        ctl.on_stream_state = lambda: self.loop.call_soon_threadsafe(self.push_state)
        self.updater = Updater(on_change=self.push_state)
        handler = _SseLogHandler(self)
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)

    # ------------------------------------------------------------------ eventos
    def emit(self, event: dict[str, Any]) -> None:
        for q in list(self._clients):
            if q.qsize() < 500:
                q.put_nowait(event)

    def emit_threadsafe(self, event: dict[str, Any]) -> None:
        self.loop.call_soon_threadsafe(self.emit, event)

    def toast(self, message: str, kind: str = "info") -> None:
        self.emit({"type": "toast", "kind": kind, "message": message})

    def state(self) -> dict[str, Any]:
        devices = sorted(self.ctl.devices.devices.values(), key=lambda d: (d.kind, d.name.lower()))
        return {
            "app": APP_NAME,
            "version": __version__,
            "platform": sys.platform,
            "scanning": self._scanning,
            "devices": [_device_json(d) for d in devices],
            "audio": {"active": list(self.ctl.audio_tasks), "source": self.ctl.audio_hub.speaker_name},
            "video": {"active": list(self.ctl.video_tasks), "screen": list(self.ctl.hls_jobs)},
            "receiver": {"running": self.receiver.running},
            "settings": {k: SETTINGS.get(k) for k in SETTING_KEYS},
            "deps": {"uxplay": find_uxplay(), "ffmpeg": find_ffmpeg(), "bonjour": find_bonjour()},
            "installing": sorted(self._installing),
            "encoders": ENCODERS,
            "canPickFiles": self.pick_file is not None,
            "update": self.updater.as_dict(),
        }

    def push_state(self) -> None:
        self.emit({"type": "state", "data": self.state()})
        active = bool(self.ctl.audio_tasks) or bool(self.ctl.hls_jobs)
        if active and (self._level_task is None or self._level_task.done()):
            self._level_task = asyncio.ensure_future(self._level_loop())

    async def _level_loop(self) -> None:
        while self.ctl.audio_tasks or self.ctl.hls_jobs:
            self.emit({"type": "level", "value": round(min(1.0, self.ctl.audio_hub.level), 3)})
            await asyncio.sleep(0.1)
        self.emit({"type": "level", "value": 0})

    def _receiver_exited(self, code: int) -> None:
        self.emit({"type": "receiver", "line": f"— UxPlay se detuvo (código {code}) —"})
        if code not in (0, 1, -15, 15):
            self.toast(f"El receptor se cerró inesperadamente (código {code}). Mira el registro.", "error")
        self.push_state()

    # ------------------------------------------------------------------ servidor
    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._auth])
        r = app.router
        r.add_get("/api/state", lambda req: self._ok(self.state()))
        r.add_get("/api/events", self._events)
        r.add_post("/api/scan", self._scan)
        r.add_post("/api/pair/begin", self._pair_begin)
        r.add_post("/api/pair/finish", self._pair_finish)
        r.add_post("/api/pair/cancel", self._pair_cancel)
        r.add_post("/api/forget", self._forget)
        r.add_get("/api/audio/outputs", self._audio_outputs)
        r.add_post("/api/audio/source", self._audio_source)
        r.add_post("/api/audio/start", self._audio_start)
        r.add_post("/api/audio/stop", self._audio_stop)
        r.add_post("/api/volume", self._volume)
        r.add_get("/api/volume", self._get_volume)
        r.add_post("/api/video/url", self._video_url)
        r.add_post("/api/video/file", self._video_file)
        r.add_post("/api/video/stop", self._video_stop)
        r.add_get("/api/monitors", lambda req: self._ok(list_monitors()))
        r.add_post("/api/screen/start", self._screen_start)
        r.add_post("/api/remote", self._remote)
        r.add_get("/api/nowplaying", self._now_playing)
        r.add_get("/api/apps", self._apps)
        r.add_post("/api/apps/launch", self._launch)
        r.add_post("/api/keyboard", self._keyboard)
        r.add_post("/api/receiver/start", self._receiver_start)
        r.add_post("/api/receiver/stop", self._receiver_stop)
        r.add_post("/api/settings", self._settings)
        r.add_post("/api/pick", self._pick)
        r.add_post("/api/deps/install", self._install_dep)
        r.add_post("/api/update/check", self._update_check)
        r.add_post("/api/update/download", self._update_download)
        r.add_post("/api/update/install", self._update_install)
        r.add_get("/", self._index)
        if WEB_DIR.exists():
            r.add_static("/assets", WEB_DIR / "assets")
            r.add_get("/{name}", self._static_file)
        return app

    async def start(self, port: int = 47800) -> None:
        runner = web.AppRunner(self.app(), access_log=None)
        await runner.setup()
        for p in range(port, port + 30):
            try:
                await web.TCPSite(runner, "127.0.0.1", p).start()
                self.port = p
                break
            except OSError:
                continue
        else:
            raise RuntimeError("No hay puertos libres para la interfaz")
        log.info("Interfaz disponible en %s", self.url)
        self.updater.start_background()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    @web.middleware
    async def _auth(self, request: web.Request, handler: Any) -> web.StreamResponse:
        if request.path.startswith("/api/"):
            token = request.headers.get("X-Token") or request.query.get("t")
            if not token or not secrets.compare_digest(token, self.token):
                raise web.HTTPUnauthorized()
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                log.exception("Error en %s", request.path)
                return web.json_response({"error": str(exc) or type(exc).__name__}, status=400)
        return await handler(request)

    async def _index(self, request: web.Request) -> web.StreamResponse:
        index = WEB_DIR / "index.html"
        if not index.exists():
            return web.Response(text="Falta compilar la interfaz: cd frontend && npm run build", status=500)
        html = index.read_text("utf-8").replace(
            "</head>", f"<script>window.__AIRWIN_TOKEN__={json.dumps(self.token)}</script></head>", 1)
        return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})

    async def _static_file(self, request: web.Request) -> web.StreamResponse:
        target = (WEB_DIR / request.match_info["name"]).resolve()
        if target.parent != WEB_DIR.resolve() or not target.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(target)

    @staticmethod
    def _ok(data: Any = None) -> web.Response:
        return web.json_response({"ok": True} if data is None else data)

    async def _events(self, request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(request)
        q: asyncio.Queue = asyncio.Queue()
        self._clients.add(q)
        q.put_nowait({"type": "state", "data": self.state()})
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    await resp.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                except asyncio.TimeoutError:
                    await resp.write(b": ping\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self._clients.discard(q)
        return resp

    # ------------------------------------------------------------------ dispositivos
    async def _scan(self, request: web.Request) -> web.Response:
        if not self._scanning:
            self._scanning = True
            self.push_state()
            try:
                devices = await self.ctl.devices.scan(5)
                log.info("Búsqueda completa: %d dispositivos", len(devices))
            finally:
                self._scanning = False
                self.push_state()
        return self._ok()

    async def _pair_begin(self, request: web.Request) -> web.Response:
        body = await request.json()
        ident, proto = body["id"], Protocol[body["protocol"]]
        handler = await self.ctl.devices.begin_pairing(ident, proto)
        sid = secrets.token_hex(8)
        self._pairing[sid] = (ident, handler)
        pin = None if handler.device_provides_pin else f"{secrets.randbelow(10000):04d}"
        if pin:
            self._pairing[sid] = (ident, (handler, pin))
        return self._ok({"session": sid, "deviceProvidesPin": handler.device_provides_pin, "pin": pin})

    async def _pair_finish(self, request: web.Request) -> web.Response:
        body = await request.json()
        ident, entry = self._pairing.pop(body["session"])
        handler, pin = entry if isinstance(entry, tuple) else (entry, body.get("pin"))
        ok = await self.ctl.devices.finish_pairing(ident, handler, str(pin or "").strip() or None)
        self.push_state()
        if not ok:
            raise RuntimeError("No se pudo emparejar. Revisa el PIN e inténtalo de nuevo.")
        return self._ok()

    async def _pair_cancel(self, request: web.Request) -> web.Response:
        body = await request.json()
        item = self._pairing.pop(body.get("session", ""), None)
        if item:
            handler = item[1][0] if isinstance(item[1], tuple) else item[1]
            await handler.close()
        return self._ok()

    async def _forget(self, request: web.Request) -> web.Response:
        ident = (await request.json())["id"]
        self.ctl.devices.forget(ident)
        await self.ctl.devices.disconnect(ident)
        self.push_state()
        return self._ok()

    # ------------------------------------------------------------------ audio
    async def _audio_outputs(self, request: web.Request) -> web.Response:
        try:
            outputs = await asyncio.get_running_loop().run_in_executor(None, self.ctl.audio_hub.list_outputs)
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudieron listar las salidas de audio: %s", exc)
            outputs = []
        return self._ok(outputs)

    async def _audio_source(self, request: web.Request) -> web.Response:
        self.ctl.audio_hub.speaker_name = (await request.json()).get("name") or None
        self.push_state()
        return self._ok()

    async def _audio_start(self, request: web.Request) -> web.Response:
        body = await request.json()
        ids: list[str] = body["ids"]
        if not ids:
            raise RuntimeError("Elige al menos un altavoz")
        await self.ctl.stream_audio(ids, body.get("file") or None)
        if body.get("volume") is not None:
            for i in ids:
                try:
                    await self.ctl.set_volume(i, float(body["volume"]))
                except Exception as exc:  # noqa: BLE001
                    log.debug("volumen: %s", exc)
        return self._ok()

    async def _audio_stop(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        await self.ctl.stop_audio(body.get("id"))
        return self._ok()

    async def _volume(self, request: web.Request) -> web.Response:
        body = await request.json()
        errors = []
        for i in body["ids"]:
            try:
                await self.ctl.set_volume(i, float(body["level"]))
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if errors and len(errors) == len(body["ids"]):
            raise RuntimeError(errors[0])
        return self._ok()

    async def _get_volume(self, request: web.Request) -> web.Response:
        return self._ok({"level": await self.ctl.get_volume(request.query["id"])})

    # ------------------------------------------------------------------ video / pantalla
    async def _video_url(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.ctl.play_url(body["id"], body["url"])
        return self._ok()

    async def _video_file(self, request: web.Request) -> web.Response:
        body = await request.json()
        if not Path(body["path"]).is_file():
            raise RuntimeError("El archivo no existe")
        await self.ctl.play_file(body["id"], body["path"], bool(body.get("convert")))
        return self._ok()

    async def _video_stop(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        await self.ctl.stop_video(body.get("id"))
        return self._ok()

    async def _screen_start(self, request: web.Request) -> web.Response:
        body = await request.json()
        for key in ("cast_fps", "cast_encoder", "cast_bitrate"):
            if key in body:
                SETTINGS.set(key, body[key])
        if not find_ffmpeg():
            raise RuntimeError("Falta ffmpeg. Instálalo desde Configuración → Componentes.")
        rect = tuple(int(v) for v in body["rect"])
        await self.ctl.cast_screen(body["id"], rect, bool(body.get("audio")))  # type: ignore[arg-type]
        return self._ok()

    # ------------------------------------------------------------------ mando
    async def _remote(self, request: web.Request) -> web.Response:
        body = await request.json()
        allowed = {"up", "down", "left", "right", "select", "menu", "home", "play_pause", "next", "previous",
                   "volume_up", "volume_down", "turn_on", "turn_off", "skip_forward", "skip_backward",
                   "top_menu", "play", "pause", "stop", "home_hold"}
        if body["action"] not in allowed:
            raise RuntimeError("Acción no válida")
        await self.ctl.remote(body["id"], body["action"])
        return self._ok()

    async def _now_playing(self, request: web.Request) -> web.Response:
        ident = request.query["id"]
        atv = await self.ctl.devices.connect(ident)
        playing = await atv.metadata.playing()
        app_name = None
        try:
            app_name = atv.metadata.app.name if atv.metadata.app else None
        except Exception:  # noqa: BLE001
            pass
        artwork = None
        return self._ok({
            "title": playing.title, "artist": playing.artist, "album": playing.album,
            "state": playing.device_state.name if playing.device_state else None,
            "position": playing.position, "total": playing.total_time, "app": app_name, "artwork": artwork,
        })

    async def _apps(self, request: web.Request) -> web.Response:
        apps = await self.ctl.list_apps(request.query["id"])
        return self._ok([{"name": n, "id": i} for n, i in apps])

    async def _launch(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.ctl.launch_app(body["id"], body["app"])
        return self._ok()

    async def _keyboard(self, request: web.Request) -> web.Response:
        body = await request.json()
        await self.ctl.send_text(body["id"], body["text"])
        return self._ok()

    # ------------------------------------------------------------------ receptor
    async def _receiver_start(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else {}
        for key, value in body.items():
            if key in SETTING_KEYS:
                SETTINGS.set(key, value)
        self.receiver.start()
        self.toast(f"Receptor activo: «{SETTINGS.get('receiver_name')}»", "success")
        self.push_state()
        return self._ok()

    async def _receiver_stop(self, request: web.Request) -> web.Response:
        await asyncio.get_running_loop().run_in_executor(None, self.receiver.stop)
        self.push_state()
        return self._ok()

    # ------------------------------------------------------------------ ajustes
    async def _settings(self, request: web.Request) -> web.Response:
        for key, value in (await request.json()).items():
            if key in SETTING_KEYS:
                SETTINGS.set(key, value)
        self.push_state()
        return self._ok()

    async def _pick(self, request: web.Request) -> web.Response:
        if not self.pick_file:
            raise RuntimeError("Selector de archivos no disponible: escribe la ruta a mano.")
        kind = (await request.json()).get("kind", "any")
        path = await asyncio.get_running_loop().run_in_executor(None, self.pick_file, kind)
        return self._ok({"path": path})

    async def _install_dep(self, request: web.Request) -> web.Response:
        name = (await request.json())["name"]
        if name not in WINGET_IDS:
            raise RuntimeError("Dependencia desconocida")
        if sys.platform != "win32":
            raise RuntimeError("La instalación automática sólo está disponible en Windows")
        if name in self._installing:
            return self._ok()
        self._installing.add(name)
        self.push_state()
        asyncio.ensure_future(self._run_winget(name))
        return self._ok()

    async def _run_winget(self, name: str) -> None:
        cmd = ["winget", "install", "--id", WINGET_IDS[name], "--exact", "--silent",
               "--accept-package-agreements", "--accept-source-agreements"]
        log.info("Instalando %s: %s", name, " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                creationflags=0x08000000,
            )
            assert proc.stdout
            async for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if line and not set(line) <= set("-\\|/ █▒"):
                    log.info("winget: %s", line)
            code = await proc.wait()
            # winget devuelve 0 o "ya instalado" (0x8A15002B)
            if code in (0, -1978335189, 2316632107):
                self.toast(f"{name} instalado correctamente", "success")
            else:
                self.toast(f"No se pudo instalar {name} (código {code}). Mira el registro.", "error")
        except FileNotFoundError:
            self.toast("winget no está disponible. Instala «App Installer» desde Microsoft Store.", "error")
        finally:
            self._installing.discard(name)
            self.push_state()

    # ------------------------------------------------------------------ actualizaciones
    async def _update_check(self, request: web.Request) -> web.Response:
        await self.updater.check()
        if self.updater.state.status == "uptodate":
            self.toast(f"AirWin {self.updater.state.current} es la versión más reciente", "success")
        return self._ok()

    async def _update_download(self, request: web.Request) -> web.Response:
        if not self.updater.state.can_install:
            raise RuntimeError("Esta copia no se puede actualizar sola. Descarga la nueva versión desde GitHub.")
        await self.updater.download()
        return self._ok()

    async def _update_install(self, request: web.Request) -> web.Response:
        self.updater.install()
        # Dar tiempo a que la respuesta llegue a la interfaz y cerrar la app.
        await self.shutdown()
        if self.quit_app:
            self.loop.call_later(0.8, self.quit_app)
        return self._ok()

    async def shutdown(self) -> None:
        await asyncio.get_running_loop().run_in_executor(None, self.receiver.stop)


class _SseLogHandler(logging.Handler):
    def __init__(self, server: ApiServer) -> None:
        super().__init__()
        self.server = server
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.server.emit_threadsafe({
                "type": "log", "level": record.levelname.lower(), "time": record.created,
                "message": self.format(record),
            })
        except RuntimeError:
            pass
