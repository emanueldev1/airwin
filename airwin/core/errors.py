"""Mensajes de error comprensibles para el usuario."""
from __future__ import annotations

import asyncio
from typing import Optional


def friendly_error(exc: BaseException) -> str:
    """Convierte excepciones técnicas en mensajes comprensibles."""
    from pyatv import exceptions as ex

    chain = []
    e: Optional[BaseException] = exc
    while e is not None and len(chain) < 5:
        chain.append(e)
        e = e.__cause__ or e.__context__
    for e in chain:
        if isinstance(e, ex.AuthenticationError):
            return "El dispositivo rechazó la conexión. Vuelve a emparejarlo desde Dispositivos."
        if isinstance(e, ex.NoCredentialsError):
            return "Hay que emparejar este dispositivo antes de usarlo (Dispositivos → Emparejar)."
        if isinstance(e, ex.NotSupportedError):
            return "Este dispositivo no admite esa función."
        if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
            return "El dispositivo no respondió a tiempo. Comprueba que esté encendido y en la misma red."
        if isinstance(e, (ConnectionRefusedError, OSError)) and not isinstance(e, ex.ProtocolError):
            if getattr(e, "errno", None) is not None:
                return "No se pudo conectar con el dispositivo. Comprueba que esté encendido y en la misma red."
    if isinstance(exc, ex.ProtocolError):
        return "No se pudo establecer la conexión con el dispositivo. Mira el Registro para más detalles."
    return str(exc) or type(exc).__name__
