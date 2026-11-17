"""Captura del sonido del PC (WASAPI loopback) y envío en vivo por AirPlay.

pyatv sólo sabe abrir archivos/URLs/buffers decodificables, así que
registramos una fuente PCM propia (`LiveAudioSource`) que pyatv acepta
directamente en `atv.stream.stream_file(...)`.
"""
from __future__ import annotations

import array
import logging
import sys
import threading
import time
from collections import deque
from typing import Optional

import pyatv.protocols.raop as _raop
import pyatv.protocols.raop.protocols as _raop_protocols
import pyatv.protocols.raop.stream_client as _raop_stream
from pyatv.protocols.raop import timing as _timing
from pyatv.interface import MediaMetadata
from pyatv.protocols.raop.audio_source import AudioSource

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_SIZE = 2  # bytes (int16)
BYTES_PER_FRAME = CHANNELS * SAMPLE_SIZE
# Búfer entre la captura y el envío. Si crece (relojes que derivan), se recorta para
# que el retraso nunca se acumule.
MAX_BUFFER_SECONDS = 0.2
TRIM_TO_SECONDS = 0.06
# Al empezar a enviar se descarta lo capturado mientras se conectaba.
START_KEEP_SECONDS = 0.03

# Retraso de AirPlay (muestras a 44,1 kHz). pyatv usa 1,5 s por defecto.
LATENCY_PRESETS = {"low": 22050, "balanced": 44100, "stable": 66150}


class LiveAudioSource(AudioSource):
    """Fuente PCM alimentada desde otro hilo. Nunca termina hasta close()."""

    def __init__(self, hub: "SystemAudioHub", title: str = "Sonido del PC") -> None:
        self._hub = hub
        self._title = title
        self._chunks: deque[bytes] = deque()
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False
        self._started = False
        # Diagnóstico (se escribe en Registro cada 15 s)
        self._stat_t = time.monotonic()
        self._stat_padded = 0
        self._stat_max = 0

    def _trim(self, keep_seconds: float) -> None:
        # Llamar con self._lock tomado.
        keep = int(keep_seconds * SAMPLE_RATE) * BYTES_PER_FRAME
        while self._size > keep and self._chunks:
            excess = self._size - keep
            chunk = self._chunks[0]
            if len(chunk) <= excess:
                self._chunks.popleft()
                self._size -= len(chunk)
            else:
                cut = excess - excess % BYTES_PER_FRAME
                self._chunks[0] = chunk[cut:]
                self._size -= cut
                break

    # -- llamado desde el hilo de captura --
    def push(self, data: bytes) -> None:
        with self._lock:
            self._chunks.append(data)
            self._size += len(data)
            if self._size > int(MAX_BUFFER_SECONDS * SAMPLE_RATE) * BYTES_PER_FRAME:
                self._trim(TRIM_TO_SECONDS)

    # -- interfaz AudioSource de pyatv --
    def check_format(self, sample_rate: int, channels: int, sample_size: int) -> None:
        if (sample_rate, channels, sample_size) != (SAMPLE_RATE, CHANNELS, SAMPLE_SIZE):
            raise RuntimeError(
                f"Formato de audio no soportado por el receptor: {sample_rate} Hz, "
                f"{channels} canales, {sample_size * 8} bits"
            )

    async def readframes(self, nframes: int) -> bytes:
        if self._closed:
            return AudioSource.NO_FRAMES
        wanted = nframes * BYTES_PER_FRAME
        out = bytearray()
        with self._lock:
            if not self._started:
                self._started = True
                self._trim(START_KEEP_SECONDS)
            while self._chunks and len(out) < wanted:
                chunk = self._chunks.popleft()
                need = wanted - len(out)
                if len(chunk) > need:
                    out += chunk[:need]
                    self._chunks.appendleft(chunk[need:])
                else:
                    out += chunk
            self._size -= len(out)
            buffered = self._size
        if len(out) < wanted:  # subdesbordamiento: rellenar con silencio
            self._stat_padded += wanted - len(out)
            out += bytes(wanted - len(out))
        self._stat_max = max(self._stat_max, buffered)
        if time.monotonic() - self._stat_t >= 15:
            ms = 1000 / (SAMPLE_RATE * BYTES_PER_FRAME)
            log.info("Audio en vivo: búfer máx. %d ms · silencio insertado %d ms en 15 s",
                     self._stat_max * ms, self._stat_padded * ms)
            self._stat_t = time.monotonic()
            self._stat_padded = self._stat_max = 0
        # AirPlay (L16) espera las muestras en big-endian, igual que las fuentes de
        # pyatv (_to_audio_samples). Capturamos en little-endian: hay que invertir.
        samples = array.array("h", bytes(out))
        if sys.byteorder == "little":
            samples.byteswap()
        return samples.tobytes()

    async def get_metadata(self) -> MediaMetadata:
        return MediaMetadata(title=self._title, artist="AirWin", album="Windows")

    async def close(self) -> None:
        self._closed = True
        self._hub.unsubscribe(self)

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def channels(self) -> int:
        return CHANNELS

    @property
    def sample_size(self) -> int:
        return SAMPLE_SIZE

    @property
    def duration(self) -> int:
        return 0


class SystemAudioHub:
    """Captura una vez el audio del sistema y lo reparte a todas las salidas."""

    def __init__(self) -> None:
        self._subs: list = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.speaker_name: Optional[str] = None  # None = altavoz predeterminado
        self.level = 0.0  # nivel de pico para el vúmetro

    @staticmethod
    def list_outputs() -> list[str]:
        import soundcard as sc

        return [s.name for s in sc.all_speakers()]

    def subscribe(self, title: str = "Sonido del PC") -> LiveAudioSource:
        src = LiveAudioSource(self, title)
        self.add_sink(src)
        return src

    def add_sink(self, sink) -> None:  # type: ignore[no-untyped-def]
        """`sink` es cualquier objeto con un método push(bytes) (thread-safe)."""
        with self._lock:
            self._subs.append(sink)
            self._stop.clear()
            self._ensure_thread()

    def _ensure_thread(self) -> None:
        # Llamar con self._lock tomado.
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._capture, name="airwin-loopback", daemon=True)
            self._thread.start()

    def unsubscribe(self, src) -> None:  # type: ignore[no-untyped-def]
        with self._lock:
            if src in self._subs:
                self._subs.remove(src)
            if not self._subs:
                self._stop.set()

    def _capture(self) -> None:
        failed = False
        try:
            import numpy as np
            import soundcard as sc

            speaker = sc.default_speaker() if not self.speaker_name else sc.get_speaker(self.speaker_name)
            mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            log.info("Capturando audio de: %s", speaker.name)
            block = 441  # 10 ms
            with mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS, blocksize=block) as rec:
                while not self._stop.is_set():
                    data = rec.record(numframes=block)
                    if data.size == 0:
                        time.sleep(0.005)
                        continue
                    if data.ndim == 1:
                        data = np.column_stack([data, data])
                    elif data.shape[1] == 1:
                        data = np.repeat(data, 2, axis=1)
                    elif data.shape[1] > 2:
                        data = data[:, :2]
                    self.level = float(np.abs(data).max()) if data.size else 0.0
                    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2").tobytes()
                    with self._lock:
                        subs = list(self._subs)
                    for s in subs:
                        s.push(pcm)
        except Exception as exc:  # noqa: BLE001
            failed = True
            log.error("No se pudo capturar el sonido del PC (%s). Se enviará silencio.",
                      exc or type(exc).__name__)
            log.debug("detalle", exc_info=True)
        finally:
            self.level = 0.0
            log.info("Captura de audio detenida")
            with self._lock:
                # Alguien se suscribió mientras parábamos: volver a arrancar.
                if (not failed and self._subs and not self._stop.is_set()
                        and self._thread is threading.current_thread()):
                    self._thread = None
                    self._restart_pending = True
            if getattr(self, "_restart_pending", False):
                self._restart_pending = False
                time.sleep(1.0)  # evita bucles rápidos si el dispositivo falla
                with self._lock:
                    if self._subs and not self._stop.is_set():
                        self._ensure_thread()


class PacedPipeSink:
    """Escribe el PCM capturado en un pipe (stdin de ffmpeg) a ritmo de tiempo real.

    Si no llega audio (nada sonando) escribe silencio, para que ffmpeg nunca se quede
    esperando la pista de audio.
    """

    PERIOD = 0.02  # 20 ms

    def __init__(self, hub: SystemAudioHub, pipe) -> None:  # type: ignore[no-untyped-def]
        self._hub = hub
        self._pipe = pipe
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="airwin-pcm-pipe", daemon=True)
        hub.add_sink(self)
        self._thread.start()

    def push(self, data: bytes) -> None:
        with self._lock:
            self._buf += data
            limit = int(MAX_BUFFER_SECONDS * SAMPLE_RATE) * BYTES_PER_FRAME
            if len(self._buf) > limit:
                del self._buf[: len(self._buf) - limit]

    def _run(self) -> None:
        frames_per_period = int(SAMPLE_RATE * self.PERIOD)
        nbytes = frames_per_period * BYTES_PER_FRAME
        next_t = time.monotonic()
        try:
            while not self._stop.is_set():
                with self._lock:
                    chunk = bytes(self._buf[:nbytes])
                    del self._buf[:nbytes]
                if len(chunk) < nbytes:
                    chunk += bytes(nbytes - len(chunk))
                self._pipe.write(chunk)
                self._pipe.flush()
                next_t += self.PERIOD
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -1:  # nos quedamos muy atrás: resincronizar
                    next_t = time.monotonic()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            self._hub.unsubscribe(self)

    def close(self) -> None:
        self._stop.set()
        self._hub.unsubscribe(self)


# ---- Integración con pyatv: aceptar LiveAudioSource en stream_file ----
_original_open_source = _raop.open_source


async def _open_source(source, sample_rate, channels, sample_size):  # type: ignore[no-untyped-def]
    if isinstance(source, LiveAudioSource):
        source.check_format(sample_rate, channels, sample_size)
        return source
    return await _original_open_source(source, sample_rate, channels, sample_size)


_raop.open_source = _open_source


def _latency_frames() -> int:
    from airwin.core.config import SETTINGS

    return LATENCY_PRESETS.get(SETTINGS.get("audio_latency") or "low", LATENCY_PRESETS["low"])


_original_reset = _raop_protocols.StreamContext.reset


def _reset_with_latency(self) -> None:  # type: ignore[no-untyped-def]
    _original_reset(self)
    self.latency = _latency_frames()


_raop_protocols.StreamContext.reset = _reset_with_latency


# pyatv fija el reloj de la transmisión (start_ts) en reset(), ANTES de enviar
# metadatos, carátula, RECORD, FLUSH y volumen. Ese tiempo de conexión (D) pasa
# sin enviar audio, así que los paquetes de sincronización le dicen al receptor
# que el audio va D segundos tarde. Con audio en vivo, el HomePod compensa con un
# búfer mucho mayor. Reanclamos el reloj justo antes del primer paquete: las
# marcas RTP no cambian (start_ts y head_ts se desplazan igual), solo la hora
# real que se asocia a ellas, que pasa a ser exacta.
_original_stream_data = _raop_stream.StreamClient._stream_data


async def _stream_data_anchored(self, source, transport):  # type: ignore[no-untyped-def]
    if isinstance(source, LiveAudioSource):
        ctx = self.context
        now_ts = _timing.ntp2ts(_timing.ntp_now(), ctx.sample_rate)
        shift = now_ts - ctx.head_ts
        log.info(
            "Conexión con el receptor: %d ms · retraso de AirPlay configurado: %d ms",
            int(shift * 1000 / ctx.sample_rate),
            int(ctx.latency * 1000 / ctx.sample_rate),
        )
        if shift > 0:
            ctx.start_ts += shift
            ctx.head_ts += shift
    return await _original_stream_data(self, source, transport)


_raop_stream.StreamClient._stream_data = _stream_data_anchored
