"""Descubrimiento, conexión y emparejamiento de dispositivos Apple (pyatv)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import pyatv
from pyatv.const import PairingRequirement, Protocol
from pyatv.interface import AppleTV, BaseConfig, PairingHandler

from airwin.core.config import CREDENTIALS

log = logging.getLogger(__name__)

PROTOCOL_LABELS = {
    Protocol.AirPlay: "AirPlay (video, URL, pantalla)",
    Protocol.Companion: "Companion (mando, apps, encendido)",
    Protocol.RAOP: "RAOP (audio)",
    Protocol.MRP: "MRP (mando, tvOS antiguos)",
    Protocol.DMAP: "DMAP (Apple TV antiguos)",
}


PAIRABLE_ORDER = [Protocol.AirPlay, Protocol.Companion, Protocol.MRP, Protocol.RAOP]


@dataclass
class Device:
    identifier: str
    name: str
    address: str
    model: str
    kind: str
    protocols: list[Protocol]
    pairing: dict[Protocol, PairingRequirement] = field(default_factory=dict)
    conf: Optional[BaseConfig] = None

    @property
    def can_stream_audio(self) -> bool:
        return Protocol.RAOP in self.protocols

    @property
    def can_play_video(self) -> bool:
        return Protocol.AirPlay in self.protocols and self.kind in ("Apple TV", "Mac", "TV con AirPlay")

    @property
    def can_remote(self) -> bool:
        return any(p in self.protocols for p in (Protocol.Companion, Protocol.MRP, Protocol.DMAP))

    @property
    def icon(self) -> str:
        return {
            "Apple TV": "📺",
            "HomePod": "🔊",
            "Mac": "💻",
            "TV con AirPlay": "🖥️",
        }.get(self.kind, "🎵")

    @property
    def has_screen(self) -> bool:
        """Sólo los equipos con pantalla pueden mostrar un PIN de emparejamiento."""
        return self.kind in ("Apple TV", "Mac", "TV con AirPlay")

    def pairable_protocols(self) -> list[Protocol]:
        """Protocolos que tiene sentido emparejar con un PIN.

        Los HomePod y altavoces no tienen pantalla: pyatv los autoriza solo
        (emparejamiento transitorio), así que nunca se ofrece emparejarlos.
        En un Apple TV, RAOP queda cubierto por las credenciales de AirPlay.
        """
        if not self.has_screen:
            return []
        wanted = (PairingRequirement.Mandatory, PairingRequirement.Optional)
        protos = [p for p in PAIRABLE_ORDER if self.pairing.get(p) in wanted]
        if Protocol.AirPlay in protos and Protocol.RAOP in protos:
            protos.remove(Protocol.RAOP)
        return protos

    def needs_pairing(self) -> list[Protocol]:
        stored = CREDENTIALS.get(self.identifier, {}) or {}
        return [
            proto
            for proto in self.pairable_protocols()
            if self.pairing.get(proto) == PairingRequirement.Mandatory and proto.name not in stored
        ]


def _classify(conf: BaseConfig) -> str:
    model = (conf.device_info.model_str or "").lower()
    os_name = str(conf.device_info.operating_system).lower()
    if "homepod" in model:
        return "HomePod"
    if "apple tv" in model or "appletv" in model or "tvos" in os_name:
        return "Apple TV"
    if "mac" in model or "macos" in os_name:
        return "Mac"
    airplay = conf.get_service(Protocol.AirPlay)
    if airplay is not None:
        features = airplay.properties.get("features", "")
        # Las TVs (Samsung, LG, Sony...) anuncian AirPlay con soporte de video.
        if features and conf.get_service(Protocol.RAOP) is not None and "model" in airplay.properties:
            if any(b in airplay.properties.get("manufacturer", "").lower() for b in ("samsung", "lg", "sony", "vizio", "roku")):
                return "TV con AirPlay"
    return "Altavoz AirPlay"


class DeviceManager:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.devices: dict[str, Device] = {}
        self._connections: dict[str, AppleTV] = {}
        self._connect_locks: dict[str, asyncio.Lock] = {}

    # ---------- descubrimiento ----------
    async def scan(self, timeout: int = 5) -> list[Device]:
        confs = await pyatv.scan(self.loop, timeout=timeout)
        found: dict[str, Device] = {}
        for conf in confs:
            ident = conf.identifier
            if not ident:
                continue
            self._apply_credentials(conf)
            dev = Device(
                identifier=ident,
                name=conf.name,
                address=str(conf.address),
                model=conf.device_info.model_str or "Desconocido",
                kind=_classify(conf),
                protocols=[s.protocol for s in conf.services],
                pairing={s.protocol: s.pairing for s in conf.services},
                conf=conf,
            )
            found[ident] = dev
        # Mantener conexiones de dispositivos que siguen presentes.
        for ident in list(self._connections):
            if ident not in found:
                await self.disconnect(ident)
        self.devices = found
        log.info("Encontrados %d dispositivos AirPlay", len(found))
        return sorted(found.values(), key=lambda d: (d.kind, d.name.lower()))

    # ---------- conexión ----------
    def _apply_credentials(self, conf: BaseConfig) -> None:
        stored = CREDENTIALS.get(conf.identifier, {}) or {}
        for proto_name, creds in stored.items():
            try:
                conf.set_credentials(Protocol[proto_name], creds)
            except KeyError:
                pass

    async def connect(self, ident: str) -> AppleTV:
        lock = self._connect_locks.setdefault(ident, asyncio.Lock())
        async with lock:
            if ident in self._connections:
                return self._connections[ident]
            dev = self.devices.get(ident)
            if dev is None or dev.conf is None:
                raise RuntimeError("Dispositivo no encontrado; vuelve a buscar.")
            self._apply_credentials(dev.conf)
            log.info("Conectando a %s (%s)…", dev.name, dev.address)
            atv = await pyatv.connect(dev.conf, self.loop)
            manager = self

            class _Listener(pyatv.interface.DeviceListener):
                def connection_lost(self, exception: Exception) -> None:
                    log.warning("Conexión perdida con %s: %s", dev.name, exception)
                    manager._connections.pop(ident, None)

                def connection_closed(self) -> None:
                    manager._connections.pop(ident, None)

            atv.listener = _Listener()
            self._connections[ident] = atv
            return atv

    async def disconnect(self, ident: str) -> None:
        atv = self._connections.pop(ident, None)
        if atv is not None:
            pending = atv.close()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    async def disconnect_all(self) -> None:
        for ident in list(self._connections):
            await self.disconnect(ident)

    # ---------- emparejamiento ----------
    async def begin_pairing(self, ident: str, protocol: Protocol) -> PairingHandler:
        dev = self.devices[ident]
        await self.disconnect(ident)
        handler = await pyatv.pair(dev.conf, protocol, self.loop, name="AirWin")
        await handler.begin()
        return handler

    async def finish_pairing(self, ident: str, handler: PairingHandler, pin: Optional[str]) -> bool:
        try:
            if pin:
                handler.pin(int(pin))
            await handler.finish()
            if handler.has_paired:
                creds = handler.service.credentials
                stored = dict(CREDENTIALS.get(ident, {}) or {})
                stored[handler.service.protocol.name] = creds
                CREDENTIALS.set(ident, stored)
                dev = self.devices.get(ident)
                if dev and dev.conf:
                    dev.conf.set_credentials(handler.service.protocol, creds)
                log.info("Emparejado %s con %s", handler.service.protocol.name, ident)
                return True
            return False
        finally:
            await handler.close()

    def forget(self, ident: str) -> None:
        CREDENTIALS.set(ident, {})
