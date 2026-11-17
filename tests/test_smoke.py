"""Pruebas rápidas que se ejecutan en CI antes de publicar una release.

Detectan dependencias que rompen pyatv (como srptools 2.x con el emparejamiento
transitorio de los HomePod) sin necesitar dispositivos reales.
"""
import asyncio
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_hap_transient_pairing_srp():
    from pyatv.auth.hap_srp import SRPAuthHandler
    from pyatv.protocols.airplay.auth.hap_transient import TRANSIENT_PIN
    from srptools import SRPContext, SRPServerSession, constants

    handler = SRPAuthHandler()
    handler.initialize()
    handler.step1(TRANSIENT_PIN)
    ctx = SRPContext("Pair-Setup", str(TRANSIENT_PIN), prime=constants.PRIME_3072,
                     generator=constants.PRIME_3072_GEN, hash_func=hashlib.sha512)
    _, verifier, salt = ctx.get_user_data_triplet()
    server = SRPServerSession(SRPContext("Pair-Setup", prime=constants.PRIME_3072,
                                         generator=constants.PRIME_3072_GEN, hash_func=hashlib.sha512), verifier)
    _, proof = handler.step2(bytes.fromhex(server.public), bytes.fromhex(salt))
    assert len(proof) == 64


def test_live_audio_source_pads_silence():
    from airwin.core.live_audio import LiveAudioSource, SystemAudioHub

    src = LiveAudioSource(SystemAudioHub())
    src.push(struct.pack("<hh", 1000, -1000) * 10)
    frames = asyncio.run(src.readframes(352))
    assert len(frames) == 352 * 4
    assert frames[:4] == struct.pack("<hh", 1000, -1000)
    assert frames[-4:] == b"\x00\x00\x00\x00"


def test_version_parsing():
    from airwin.core.updater import parse_version

    assert parse_version("v1.10.2") == (1, 10, 2)
    assert parse_version("1.2") > parse_version("1.1.9")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
