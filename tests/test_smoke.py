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


def test_live_audio_matches_pyatv_file_source(tmp_path=None):
    """El audio en vivo debe salir con el mismo formato exacto que la ruta de
    archivos de pyatv (la que funciona con HomePod). Si no, se oye estática."""
    import math
    import tempfile
    import wave

    from pyatv.protocols.raop.audio_source import FileSource

    from airwin.core.live_audio import LiveAudioSource, SystemAudioHub

    n = 352
    pcm = b"".join(
        struct.pack("<hh", int(12000 * math.sin(2 * math.pi * 440 * i / 44100)), int(-7000 * math.sin(i / 7)))
        for i in range(n)
    )
    path = Path(tempfile.mkdtemp()) / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(pcm)

    async def run():
        ref = await FileSource.open(str(path), 44100, 2, 2)
        expected = await ref.readframes(n)
        live = LiveAudioSource(SystemAudioHub())
        live.push(pcm)
        got = await live.readframes(n)
        return expected, got

    expected, got = asyncio.run(run())
    assert len(got) == len(expected) == n * 4
    assert got == expected, "el audio en vivo no coincide con el formato de pyatv"


def test_live_audio_pads_silence_and_trims_backlog():
    from airwin.core.live_audio import BYTES_PER_FRAME, SAMPLE_RATE, LiveAudioSource, SystemAudioHub

    src = LiveAudioSource(SystemAudioHub())
    one_sec = b"\x01\x00" * 2 * SAMPLE_RATE
    src.push(one_sec)  # 1 s acumulado mientras "conectaba"
    assert src._size <= int(0.2 * SAMPLE_RATE) * BYTES_PER_FRAME
    first = asyncio.run(src.readframes(352))
    assert len(first) == 352 * 4
    assert src._size <= int(0.03 * SAMPLE_RATE) * BYTES_PER_FRAME  # sin retraso acumulado
    for _ in range(10):
        asyncio.run(src.readframes(352))
    assert asyncio.run(src.readframes(352)) == bytes(352 * 4)  # sin datos: silencio


def test_version_parsing():
    from airwin.core.updater import parse_version

    assert parse_version("v1.10.2") == (1, 10, 2)
    assert parse_version("1.2") > parse_version("1.1.9")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
