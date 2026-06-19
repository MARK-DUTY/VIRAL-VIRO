"""
Musica de fondo AUTOMATICA y 100% LIBRE DE DERECHOS.

En vez de descargar canciones (que podrian tener copyright), aqui GENERAMOS la
musica con FFmpeg directamente en tu PC, a partir de tonos (acordes) creados con
matematicas. Como no usa ninguna grabacion ni sample de nadie, es IMPOSIBLE que
tenga problemas de derechos de autor: es musica original generada al momento.

Crea varias pistas instrumentales suaves (tipo ambiente/cinematico) que quedan
muy bien de fondo debajo de la voz. Se generan una sola vez y se guardan en
assets/music/. Despues solo se eligen al azar.
"""
from __future__ import annotations

import random
from pathlib import Path

from .assemble import _run, find_ffmpeg
from .config import settings

MUSIC_DIR = settings.assets_dir / "music"

# Cada "mood" (ambiente) es una progresion de acordes. Cada acorde son 3 notas
# (frecuencias en Hz). Estan elegidas para sonar agradables de fondo.
_MOODS: dict[str, list[list[float]]] = {
    # Inspirador / motivacional (mayor, alegre)
    "inspirador": [
        [261.63, 329.63, 392.00],   # Do mayor
        [196.00, 246.94, 293.66],   # Sol mayor
        [220.00, 261.63, 329.63],   # La menor
        [174.61, 220.00, 261.63],   # Fa mayor
    ],
    # Emotivo / sentimental (empieza menor)
    "emotivo": [
        [220.00, 261.63, 329.63],   # La menor
        [174.61, 220.00, 261.63],   # Fa mayor
        [261.63, 329.63, 392.00],   # Do mayor
        [196.00, 246.94, 293.66],   # Sol mayor
    ],
    # Epico / cinematico (menor, mas dramatico)
    "epico": [
        [146.83, 174.61, 220.00],   # Re menor
        [233.08, 293.66, 349.23],   # Si bemol mayor
        [174.61, 220.00, 261.63],   # Fa mayor
        [130.81, 164.81, 196.00],   # Do mayor (grave)
    ],
    # Tranquilo / suave (acordes con septima, relajado)
    "tranquilo": [
        [261.63, 329.63, 392.00],   # Do
        [293.66, 349.23, 440.00],   # Re menor-ish
        [220.00, 261.63, 329.63],   # La menor
        [196.00, 246.94, 293.66],   # Sol
    ],
}


def _build_filter(chords: list[list[float]], chord_len: float) -> tuple[str, float]:
    """Construye el filtro de FFmpeg que genera la pista a partir de los acordes."""
    parts: list[str] = []
    labels: list[str] = []
    idx = 0
    for ci, chord in enumerate(chords):
        start_s = ci * chord_len
        start_ms = int(start_s * 1000)
        for freq in chord:
            src = f"n{idx}"
            out = f"c{idx}"
            # Generamos un tono (sine) del largo del acorde...
            parts.append(f"sine=frequency={freq:.2f}:duration={chord_len:.2f}[{src}]")
            # ...lo retrasamos a su lugar y le ponemos entrada/salida suave (sin clics)
            parts.append(
                f"[{src}]adelay={start_ms}:all=1,"
                f"afade=t=in:st={start_s:.2f}:d=0.30,"
                f"afade=t=out:st={start_s + chord_len - 0.40:.2f}:d=0.40[{out}]"
            )
            labels.append(f"[{out}]")
            idx += 1

    total = len(chords) * chord_len
    # Mezclamos todas las notas, bajamos volumen, damos un latido suave (tremolo),
    # suavizamos agudos (lowpass) y evitamos saturacion (alimiter).
    mix = (
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        + "volume=0.45,tremolo=f=5:d=0.12,lowpass=f=3000,alimiter=limit=0.9[out]"
    )
    parts.append(mix)
    return ";".join(parts), total


def generate_track(name: str, chords: list[list[float]], out_path: Path, chord_len: float = 4.0) -> bool:
    """Genera UNA pista de musica y la guarda en out_path (.mp3). True si ok."""
    try:
        ffmpeg = find_ffmpeg()
    except Exception:
        return False
    filt, total = _build_filter(chords, chord_len)
    cmd = [
        ffmpeg, "-y",
        "-filter_complex", filt,
        "-map", "[out]",
        "-t", f"{total:.2f}",
        "-c:a", "libmp3lame", "-q:a", "4",
        str(out_path.resolve()),
    ]
    try:
        _run(cmd)
        return out_path.exists() and out_path.stat().st_size > 1024
    except Exception as exc:  # noqa: BLE001
        print(f"[musica] no se pudo generar '{name}': {exc}")
        return False


def ensure_default_music() -> list[Path]:
    """
    Se asegura de que existan las pistas automaticas. Si no existen, las genera
    (una sola vez). Devuelve la lista de pistas disponibles.
    """
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(MUSIC_DIR.glob("auto_*.mp3"))
    if existing:
        return existing

    print("[musica] generando musica de fondo libre de derechos (solo la primera vez)...")
    created: list[Path] = []
    for name, chords in _MOODS.items():
        dest = MUSIC_DIR / f"auto_{name}.mp3"
        if generate_track(name, chords, dest):
            created.append(dest)
            print(f"[musica] creada: {dest.name}")
    return created or sorted(MUSIC_DIR.glob("auto_*.mp3"))


def pick_auto_music(seed: int | None = None) -> Path | None:
    """Devuelve una pista automatica al azar (generandolas si hace falta)."""
    tracks = ensure_default_music()
    if not tracks:
        return None
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(tracks)
