"""
Paso 3 del pipeline: convertir el guion en VOZ (audio) en espanol.

Usa Edge TTS (Microsoft), que es GRATIS e ILIMITADO y suena muy natural.
Ademas de generar el audio .mp3, capturamos el tiempo exacto en el que se
pronuncia cada palabra. Eso nos sirve para que los subtitulos aparezcan
perfectamente sincronizados (estilo CapCut / videos virales).
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import edge_tts


@dataclass
class WordTiming:
    """Una palabra y cuando se dice (en segundos)."""
    word: str
    start: float   # segundo en que empieza
    end: float     # segundo en que termina


@dataclass
class VoiceResult:
    audio_path: Path
    words: list[WordTiming]
    duration: float   # duracion total del audio en segundos


def _ticks_to_seconds(ticks: int) -> float:
    # Edge TTS reporta el tiempo en "ticks" de 100 nanosegundos
    return ticks / 10_000_000.0


def _make_communicate(text: str, voice: str, rate: str):
    """
    Crea el objeto de Edge TTS pidiendo EXPLICITAMENTE los tiempos por PALABRA
    ("WordBoundary"). Esto es CLAVE para los subtitulos: las versiones nuevas de
    edge-tts (7.x) por defecto mandan solo "SentenceBoundary" (por frase), y si
    no pedimos WordBoundary nos quedamos sin tiempos de palabra -> los subtitulos
    caian al 'Plan B' (reparto parejo) y se iban ATRASANDO poco a poco.

    Las versiones viejas (6.x) no aceptan el parametro 'boundary' pero ya mandan
    WordBoundary por defecto, asi que si falla lo creamos sin ese parametro.
    """
    try:
        return edge_tts.Communicate(text=text, voice=voice, rate=rate, boundary="WordBoundary")
    except TypeError:
        return edge_tts.Communicate(text=text, voice=voice, rate=rate)


def _norm_word(s: str) -> str:
    """Version comparable de una palabra: minusculas y solo letras/numeros."""
    return re.sub(r"[^0-9a-záéíóúüñ]", "", (s or "").lower())


def _reattach_punctuation(text: str, words: list[WordTiming]) -> list[WordTiming]:
    """
    El motor de voz (Edge TTS) nos da cada palabra SIN signos de puntuacion, por
    eso los subtitulos salian sin puntos, ni ¿? ni ¡!. Aqui volvemos a pegarle a
    cada palabra los signos que tenia en el guion ORIGINAL (puntos, exclamacion,
    interrogacion, acentos), conservando su tiempo. Las comas ya no vienen en el
    texto (se quitaron antes), asi que los subtitulos quedan con todo MENOS comas.

    ROBUSTO: a veces el motor de voz junta VARIAS palabras del texto en un solo
    "tiempo" (ej: los numeros: "1999 pesos" llega como una sola pieza). Por eso
    NO exigimos que los conteos coincidan: recorremos el texto original palabra
    por palabra y a cada pieza de tiempo le asignamos TANTAS palabras del texto
    como palabras tenga esa pieza. Asi la puntuacion queda bien colocada aunque
    los numeros o las fechas se agrupen.

    Es a prueba de fallos: si al final la alineacion se ve dudosa (las palabras
    no cuadran), dejamos los subtitulos tal cual (no arriesgamos romper nada).
    """
    tokens = (text or "").split()
    if not tokens or not words:
        return words

    result: list[WordTiming] = []
    ti = 0                      # posicion en las palabras del texto original
    ok = 0                      # cuantas piezas quedaron bien alineadas
    total = 0
    for w in words:
        n = max(1, len((w.word or "").split()))   # cuantas palabras cubre este tiempo
        chunk = tokens[ti : ti + n]
        ti += n
        if chunk:
            display = " ".join(chunk)
            total += 1
            if _norm_word(display) == _norm_word(w.word):
                ok += 1
            result.append(WordTiming(word=display, start=w.start, end=w.end))
        else:
            result.append(w)

    # Si sobraron palabras del texto (el motor junto de mas), las pegamos a la
    # ultima pieza para no perder texto ni su puntuacion final.
    if ti < len(tokens) and result:
        last = result[-1]
        extra = " ".join(tokens[ti:]).strip()
        result[-1] = WordTiming(word=(last.word + " " + extra).strip(), start=last.start, end=last.end)

    # Sanidad: si casi nada coincidio, la alineacion salio mal -> no tocamos nada.
    if total and ok < max(1, int(0.6 * total)):
        return words
    return result


def _words_from_sentences(sentences: list[tuple[float, float, str]]) -> list[WordTiming]:
    """
    Respaldo: si SOLO recibimos tiempos por FRASE (no por palabra), repartimos
    las palabras DENTRO del tiempo real de su frase (proporcional a su largo).
    Queda mucho mejor sincronizado que repartir todo el texto parejo, y NO se
    acumula el atraso, porque cada frase se ancla a su tiempo real del audio.
    """
    words: list[WordTiming] = []
    for s_start, s_end, text in sentences:
        toks = (text or "").split()
        if not toks:
            continue
        weights = [max(1, len(t)) for t in toks]
        total = sum(weights)
        span = max(0.05, s_end - s_start)
        t = s_start
        for tok, w in zip(toks, weights):
            dur = span * w / total
            words.append(WordTiming(word=tok, start=round(t, 3), end=round(t + dur, 3)))
            t += dur
    return words


async def _synthesize(text: str, voice: str, rate: str, out_path: Path) -> list[WordTiming]:
    communicate = _make_communicate(text, voice, rate)
    words: list[WordTiming] = []
    sentences: list[tuple[float, float, str]] = []

    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            ctype = chunk.get("type")
            if ctype == "audio":
                f.write(chunk["data"])
            elif ctype == "WordBoundary":
                start = _ticks_to_seconds(chunk["offset"])
                dur = _ticks_to_seconds(chunk["duration"])
                words.append(
                    WordTiming(
                        word=chunk.get("text", ""),
                        start=round(start, 3),
                        end=round(start + dur, 3),
                    )
                )
            elif ctype == "SentenceBoundary":
                start = _ticks_to_seconds(chunk["offset"])
                dur = _ticks_to_seconds(chunk["duration"])
                sentences.append((start, start + dur, chunk.get("text", "")))

    # Si no hubo tiempos por palabra (version que solo manda por frase), los
    # derivamos de las frases (mejor que el reparto parejo global).
    if not words and sentences:
        words = _words_from_sentences(sentences)
    return words


def synthesize_voice(
    text: str,
    voice: str,
    out_path: Path,
    rate: str = "+0%",
) -> VoiceResult:
    """
    Genera el audio del texto y devuelve la ruta + los tiempos de cada palabra.

    Funciona en Windows sin problemas (maneja el bucle de asyncio por dentro).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = (text or "").strip()
    if not text:
        raise ValueError("No hay texto para convertir en voz.")

    words = asyncio.run(_synthesize(text, voice, rate, out_path))
    # Devolvemos a cada palabra sus signos (puntos, ¿? ¡!, acentos) para que los
    # subtitulos los muestren. Sin comas, porque el texto ya viene sin comas.
    words = _reattach_punctuation(text, words)

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise ValueError(
            "No se genero el audio. Revisa tu conexion a internet "
            "(Edge TTS necesita internet) y el nombre de la voz en .env."
        )

    duration = words[-1].end if words else 0.0
    return VoiceResult(audio_path=out_path, words=words, duration=duration)


async def _list_voices_es() -> list[dict]:
    voices = await edge_tts.list_voices()
    return [v for v in voices if v.get("Locale", "").startswith("es")]


def list_spanish_voices() -> list[dict]:
    """Lista las voces en espanol disponibles (util para la interfaz)."""
    try:
        return asyncio.run(_list_voices_es())
    except Exception:
        return []


# Frase de ejemplo para que el usuario ESCUCHE como suena una voz antes de
# elegirla. Es corta para que se genere rapido.
VOICE_SAMPLE_TEXT = (
    "Hola, asi se escuchara la narracion de tu video. "
    "Espero que esta voz te guste para tu proyecto."
)


def synthesize_voice_sample(
    voice: str,
    previews_dir: Path,
    rate: str = "+0%",
) -> Path:
    """
    Genera (o reutiliza) un audio CORTO de ejemplo con la voz indicada, para que
    el usuario la escuche antes de elegirla. Guarda el archivo en `previews_dir`
    con un nombre basado en la voz, asi la segunda vez no lo vuelve a generar
    (cache) y suena al instante.
    """
    voice = (voice or "").strip()
    if not voice:
        raise ValueError("No se indico ninguna voz para la muestra.")

    previews_dir = Path(previews_dir)
    previews_dir.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", voice)
    out_path = previews_dir / f"sample_{safe}.mp3"

    # Si ya la generamos antes, la reutilizamos (mas rapido).
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    asyncio.run(_synthesize(VOICE_SAMPLE_TEXT, voice, rate, out_path))

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise ValueError(
            "No se pudo generar la muestra de voz. Revisa tu conexion a internet "
            "(Edge TTS necesita internet) y que el nombre de la voz sea valido."
        )
    return out_path


def synthesize_scene_preview(
    text: str,
    voice: str,
    previews_dir: Path,
    rate: str = "+0%",
) -> Path:
    """
    Genera (o reutiliza) un audio con el TEXTO REAL de una escena y la voz
    indicada, para que el usuario ESCUCHE escena por escena como sonara la
    narracion (comas, entonacion, preguntas, exclamaciones) ANTES de armar el
    video final.

    Se guarda con un nombre basado en el HASH del (texto + voz + velocidad), asi:
      - Si el dialogo NO cambio, la segunda vez suena al instante (cache).
      - Si el usuario EDITA el dialogo, el hash cambia y se genera de nuevo
        automaticamente con el texto nuevo.
    """
    voice = (voice or "").strip()
    text = (text or "").strip()
    if not voice:
        raise ValueError("No se indico ninguna voz para la escena.")
    if not text:
        raise ValueError("Esta escena no tiene dialogo para escuchar.")

    previews_dir = Path(previews_dir)
    previews_dir.mkdir(parents=True, exist_ok=True)

    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:20]
    out_path = previews_dir / f"scene_{key}.mp3"

    # Si ya lo generamos con el MISMO texto y voz, lo reutilizamos (instantaneo).
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    asyncio.run(_synthesize(text, voice, rate, out_path))

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise ValueError(
            "No se pudo generar el audio de la escena. Revisa tu conexion a "
            "internet (Edge TTS necesita internet) y que la voz sea valida."
        )
    return out_path


# Voces EXTRANJERAS (hablantes no nativos) para el efecto "acento extranjero
# hablando espanol" (experimental). No suenan tan naturales en espanol como las
# voces nativas, pero dan ese toque de acento (chino, coreano, japones, ingles,
# frances, italiano, aleman, brasileno). El usuario decide si le gusta.
FOREIGN_ACCENT_VOICES = [
    {"value": "zh-CN-XiaoxiaoNeural", "label": "Acento chino (mujer) · experimental"},
    {"value": "zh-CN-YunxiNeural", "label": "Acento chino (hombre) · experimental"},
    {"value": "ko-KR-SunHiNeural", "label": "Acento coreano (mujer) · experimental"},
    {"value": "ko-KR-InJoonNeural", "label": "Acento coreano (hombre) · experimental"},
    {"value": "ja-JP-NanamiNeural", "label": "Acento japones (mujer) · experimental"},
    {"value": "ja-JP-KeitaNeural", "label": "Acento japones (hombre) · experimental"},
    {"value": "en-US-JennyNeural", "label": "Acento ingles/gringo (mujer) · experimental"},
    {"value": "en-US-GuyNeural", "label": "Acento ingles/gringo (hombre) · experimental"},
    {"value": "fr-FR-DeniseNeural", "label": "Acento frances (mujer) · experimental"},
    {"value": "it-IT-ElsaNeural", "label": "Acento italiano (mujer) · experimental"},
    {"value": "de-DE-KatjaNeural", "label": "Acento aleman (mujer) · experimental"},
    {"value": "pt-BR-FranciscaNeural", "label": "Acento brasileno (mujer) · experimental"},
]


def foreign_accent_options() -> list[dict]:
    """Devuelve la lista de voces extranjeras (para el efecto de acento)."""
    return list(FOREIGN_ACCENT_VOICES)
