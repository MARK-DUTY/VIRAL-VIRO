"""
ORQUESTADOR del pipeline, en DOS PASOS (como el editor de ViroFeed):

  PASO 1 (prepare_video):
    URL -> articulo -> guion en escenas (IA) -> voz -> imagenes por escena
    Devuelve un PreparedJob para que el usuario REVISE las imagenes.

  (el usuario puede regenerar / reemplazar imagenes que salieron mal)

  PASO 2 (assemble_prepared):
    subtitulos -> (avatar opcional) -> ensamblar video final .mp4

Asi el usuario aprueba/corrige las imagenes ANTES de armar el video.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import avatar as avatar_mod
try:
    from . import music as music_mod
except Exception:  # si falta music.py, el programa sigue funcionando (sin musica automatica)
    music_mod = None
from .article import extract_article, extract_articles
from .assemble import (
    build_video,
    concat_audio,
    extract_audio,
    has_audio_stream,
    make_silence,
    normalize_audio,
    probe_duration,
    resolution_for,
    trim_and_format_audio,
)
from .config import settings
from .images import ImageResult, fetch_scene_images, fetch_scene_videos, fetch_single_image, fetch_single_video
from .script_gen import Scene, ensure_english, generate_script, generate_script_from_story
from .subtitles import SubtitleStyle, build_ass_subtitles, build_subtitles_from_text
from .voice import WordTiming, synthesize_voice

ProgressFn = Callable[[str, int], None]


def _noop(msg: str, pct: int) -> None:
    pass


def _slugify(text: str, maxlen: int = 40) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    keep = "_".join(keep.split())
    return (keep[:maxlen] or "video").strip("_")


# Palabras que activan el modo "voz automatica" (rotacion)
_RANDOM_VOICE_WORDS = {"random", "auto", "automatica", "automática", "aleatoria", "azar", ""}

# Atajos para elegir simplemente "voz de hombre" o "voz de mujer" desde la
# pantalla de revision (sin tener que conocer el nombre exacto de la voz).
_MALE_WORDS = {"hombre", "masculino", "man", "male", "h"}
_FEMALE_WORDS = {"mujer", "femenino", "woman", "female", "m"}
DEFAULT_MALE_VOICE = "es-MX-JorgeNeural"
DEFAULT_FEMALE_VOICE = "es-MX-DaliaNeural"

# Nombres comunes de voces FEMENINAS en espanol de Edge TTS. Sirve para saber,
# a partir del nombre de la voz, si debemos usar la foto de mujer o de hombre.
_FEMALE_VOICE_NAMES = {
    "dalia", "elvira", "salome", "paloma", "larissa", "ximena", "sabina",
    "tania", "marisol", "yolanda", "nuria", "renata", "emilia", "julia",
    "camila", "valentina", "abril", "luciana", "catalina", "amanda",
    "estrella", "vera", "marta", "irene",
}


def _voice_is_female(voice: str | None) -> bool:
    """Adivina si una voz es femenina por su nombre (para escoger la foto)."""
    name = (voice or "").lower()
    return any(fn in name for fn in _FEMALE_VOICE_NAMES)


def _pick_avatar_face(assets_dir: Path, voice: str | None) -> Path:
    """
    Elige la FOTO del avatar que combina con la voz:
      - voz de mujer  -> assets/avatar_mujer.jpg  (o .png)
      - voz de hombre -> assets/avatar_hombre.jpg (o .png)
    Si no existe la foto por genero, usa assets/avatar.jpg como respaldo.
    """
    if _voice_is_female(voice):
        candidates = ["avatar_mujer.jpg", "avatar_mujer.png", "avatar.jpg", "avatar.png"]
    else:
        candidates = ["avatar_hombre.jpg", "avatar_hombre.png", "avatar.jpg", "avatar.png"]
    for name in candidates:
        p = assets_dir / name
        if p.exists():
            return p
    # No encontramos ninguna; devolvemos la ruta por defecto para que el avatar
    # muestre un mensaje claro de "falta assets/avatar.jpg".
    return assets_dir / "avatar.jpg"


def _next_rotating_voice() -> str:
    """
    Devuelve la siguiente voz del grupo (rotando en cada llamada).
    Guarda el indice en un archivito para que la rotacion continue aunque
    se cierre y se vuelva a abrir el programa.

    Ejemplo: video 1 -> voz 1, video 2 -> voz 2, ... y al llegar al final
    vuelve a empezar.
    """
    pool = [v for v in settings.voice_pool if v] or ["es-MX-JorgeNeural"]
    state_file = settings.work_dir / "voice_rotation.txt"
    try:
        idx = int(state_file.read_text(encoding="utf-8").strip())
    except Exception:
        idx = 0
    voice = pool[idx % len(pool)]
    try:
        state_file.write_text(str((idx + 1) % 1_000_000), encoding="utf-8")
    except Exception:
        pass
    print(f"[voz] modo automatico -> voz {idx % len(pool) + 1} de {len(pool)}: {voice}")
    return voice


def _resolve_voice(voice: str | None) -> str:
    """Si el usuario pidio 'voz automatica', elige la siguiente del grupo.
    Tambien entiende los atajos 'hombre' y 'mujer'."""
    v = (voice or "").strip().lower()
    if v in _RANDOM_VOICE_WORDS:
        return _next_rotating_voice()
    if v in _MALE_WORDS:
        return DEFAULT_MALE_VOICE
    if v in _FEMALE_WORDS:
        return DEFAULT_FEMALE_VOICE
    return voice  # type: ignore[return-value]


@dataclass
class PreparedJob:
    """Estado intermedio: todo listo menos el video final (a la espera de revision)."""
    job_dir: Path
    title: str
    narration: str
    scenes: list[Scene]
    images: list[ImageResult] = field(default_factory=list)  # una por escena (editable)
    audio_path: Path | None = None
    audio_words: list[WordTiming] = field(default_factory=list)
    real_duration: float = 0.0
    titles: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    image_source: str = "hybrid"
    # Tipo de fondo: "image" (fotos) o "video" (videoclips de stock).
    media_type: str = "image"
    # Aviso para el usuario cuando NO se pudo llegar a la duracion pedida
    # (por falta de material). Cadena vacia = sin aviso.
    warning: str = ""
    # Datos para poder REGENERAR la voz si el usuario edita los dialogos:
    voice: str = "es-MX-JorgeNeural"
    rate: str = "+0%"
    synth_narration: str = ""           # narracion con la que se genero el audio actual
    # --- MODO PODCAST: dos voces (A y B) conversando. ---
    podcast: bool = False
    voice_a: str = ""                   # voz de la persona A (si podcast)
    voice_b: str = ""                   # voz de la persona B (si podcast)
    speaker_a_name: str = ""            # nombre del avatar A (para mostrar)
    speaker_b_name: str = ""            # nombre del avatar B (para mostrar)
    # --- PERSONALIDAD del narrador (avatar): instrucciones de tono para la IA. ---
    style_instructions: str = ""
    persona_name: str = ""              # nombre del avatar elegido (para mostrar)
    # Musica de fondo opcional (la sube el usuario). None = sin musica.
    music_path: Path | None = None
    # Memoria de fotos de stock ya mostradas, por escena (para que "Otra foto"
    # entregue una DISTINTA en cada clic y no repita la misma).
    used_image_urls: dict[int, set] = field(default_factory=dict)

    def current_narration(self) -> str:
        """La narracion actual = union de los textos de las escenas (tras editar)."""
        return " ".join(s.text for s in self.scenes if s.text.strip()).strip()


@dataclass
class VideoJobResult:
    video_path: Path
    title: str
    narration: str
    titles: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    duration: float = 0.0
    used_avatar: bool = False
    image_source: str = "hybrid"


def _scene_durations(scenes: list[Scene], total_duration: float) -> list[float]:
    """Reparte la duracion total entre escenas, segun cuantas palabras narra cada una."""
    counts = [max(1, len(s.text.split())) for s in scenes]
    total_words = sum(counts)
    return [total_duration * (c / total_words) for c in counts]


def voice_for_scene(prepared: "PreparedJob", scene: Scene) -> str:
    """
    Devuelve que VOZ debe usar una escena:
      - En modo PODCAST: la voz A o la voz B segun quien habla (scene.speaker).
      - En modo normal: la voz unica del trabajo.
    """
    if prepared.podcast:
        if (scene.speaker or "").upper() == "B" and prepared.voice_b:
            return prepared.voice_b
        return prepared.voice_a or prepared.voice
    return prepared.voice


def planned_scene_durations(prepared: "PreparedJob") -> list[float]:
    """
    Duracion (en segundos) que tendra cada escena en el video, segun el audio
    actual. Se usa para MOSTRARLE al usuario cuanto durara cada imagen/video en
    la pantalla de revision. Si aun no hay audio, devuelve ceros.

    Las escenas marcadas con "usar el audio de mi video" (use_own_audio) duran
    lo que dura el video subido (own_audio_duration), no lo que se reparte de la
    voz del avatar.
    """
    n = len(prepared.scenes)
    if n == 0:
        return []

    # Escenas que narra el avatar (TTS) vs. escenas con audio propio del video.
    tts_scenes = [s for s in prepared.scenes if not s.use_own_audio]
    tts_total = prepared.real_duration
    if tts_total <= 0:
        base = [0.0] * n
    else:
        # Repartimos la duracion de la voz SOLO entre las escenas de avatar.
        counts = [max(1, len(s.text.split())) for s in tts_scenes]
        total_words = sum(counts) or 1
        base = []
        ti = 0
        for s in prepared.scenes:
            if s.use_own_audio:
                base.append(round(s.own_audio_duration or 0.0, 1))
            else:
                dur = tts_total * (counts[ti] / total_words)
                ti += 1
                base.append(dur)
    return base


def _fetch_media(
    scenes: list[Scene],
    images_dir: Path,
    media_type: str,
    image_source: str,
    progress: ProgressFn,
) -> list[ImageResult]:
    """
    Consigue el fondo de cada escena segun el tipo elegido:
      - "video" -> videoclips de stock (Pexels/Pixabay)
      - "mixed" -> videoclip por escena y, si no hay, una foto (lo hace
                   fetch_scene_videos, que cae a foto cuando no encuentra clip)
      - cualquier otro ("image") -> fotos/imagenes (comportamiento de siempre)
    """
    mt = (media_type or "image").lower()
    if mt in ("video", "mixed"):
        label = "videoclips" if mt == "video" else "mixto (video + foto)"
        progress(f"Consiguiendo {label}...", 60)
        print(f"[medios] tipo de fondo: {label}")
        return fetch_scene_videos(scenes, images_dir, progress=progress)
    progress(f"Generando imagenes ({image_source})...", 60)
    print(f"[medios] tipo de fondo: fotos (fuente: {image_source})")
    return fetch_scene_images(scenes, images_dir, source=image_source, progress=progress)


# ==========================================================================
#  PASO 1: preparar (guion + voz + imagenes) para revisar
# ==========================================================================
def prepare_video(
    url,
    *,
    duration: int | None = None,
    style: str | None = None,
    n_images=None,
    voice: str | None = None,
    rate: str | None = None,
    cta: str | None = None,
    image_source: str | None = None,
    media_type: str = "image",
    progress: ProgressFn = _noop,
    style_instructions: str = "",
    persona_name: str = "",
    podcast: bool = False,
    voice_a: str = "",
    voice_b: str = "",
    speaker_a_name: str = "",
    speaker_b_name: str = "",
) -> PreparedJob:
    cfg = settings
    # `url` puede ser un solo enlace (texto) o varios (lista). Normalizamos.
    urls = url if isinstance(url, list) else [url]
    duration = duration or cfg.video_duration
    voice = voice or cfg.tts_voice
    voice = _resolve_voice(voice)   # si es "automatica", elige una del grupo (rotando)
    rate = rate if rate is not None else cfg.tts_rate
    style = style or cfg.script_style
    cta = cta or cfg.call_to_action
    image_source = (image_source or cfg.image_source or "hybrid").lower()

    # En modo podcast, la voz "principal" es la de la persona A (para la muestra).
    if podcast:
        voice_a = _resolve_voice(voice_a or voice)
        voice_b = _resolve_voice(voice_b or cfg.tts_voice)
        voice = voice_a

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = cfg.work_dir / f"job_{stamp}"
    job_dir.mkdir(parents=True, exist_ok=True)
    images_dir = job_dir / "images"

    # 1) Leer la(s) noticia(s) y combinarlas
    n = len([u for u in urls if str(u).strip()])
    progress("Leyendo la noticia..." if n <= 1 else f"Leyendo {n} noticias...", 8)
    article = extract_articles(urls)

    # 2) Guion en escenas
    progress("Escribiendo el guion viral con IA...", 25)
    script = generate_script(
        article, duration=duration, style=style, cta=cta, n_images=n_images,
        style_instructions=style_instructions,
        podcast=podcast, speaker_a=speaker_a_name, speaker_b=speaker_b_name,
    )
    print(f"[guion] {len(script.scenes)} escenas generadas")

    # 3) Voz (muestra inicial con una sola voz; el ensamblaje final la ajusta
    #    por escena si es podcast o hay audio propio de video).
    progress("Generando la voz en espanol...", 45)
    audio = synthesize_voice(
        script.narration, voice=voice, rate=rate, out_path=job_dir / "voz.mp3"
    )
    real_duration = probe_duration(audio.audio_path) or audio.duration or float(duration)

    # 4) Medios por escena (fotos o videoclips)
    images = _fetch_media(script.scenes, images_dir, media_type, image_source, progress)
    for im in images:
        print(f"[medios] {im.source}: {im.query[:60]}")

    progress("Listo para revisar imagenes!", 100)

    return PreparedJob(
        job_dir=job_dir,
        title=article.title,
        narration=script.narration,
        scenes=script.scenes,
        images=images,
        audio_path=audio.audio_path,
        audio_words=audio.words,
        real_duration=real_duration,
        titles=script.titles,
        hashtags=script.hashtags,
        image_source=image_source,
        media_type=media_type,
        warning=script.warning,
        voice=voice,
        rate=rate,
        synth_narration=script.narration,
        podcast=podcast,
        voice_a=voice_a,
        voice_b=voice_b,
        speaker_a_name=speaker_a_name,
        speaker_b_name=speaker_b_name,
        style_instructions=style_instructions,
        persona_name=persona_name,
    )


# ==========================================================================
#  PASO 1 (YOUTUBE): preparar (subtitulos -> guion + voz + imagenes) a revisar
# ==========================================================================
def prepare_youtube(
    url,
    *,
    duration: int | None = None,
    style: str | None = None,
    n_images=None,
    voice: str | None = None,
    rate: str | None = None,
    cta: str | None = None,
    image_source: str | None = None,
    media_type: str = "image",
    progress: ProgressFn = _noop,
    style_instructions: str = "",
    persona_name: str = "",
    podcast: bool = False,
    voice_a: str = "",
    voice_b: str = "",
    speaker_a_name: str = "",
    speaker_b_name: str = "",
) -> PreparedJob:
    """
    Igual que prepare_video, pero el texto sale de uno o VARIOS VIDEOS DE YOUTUBE
    (sus subtitulos) en vez de una noticia. El resto del flujo es identico.
    """
    # Import "perezoso" y RESILIENTE: si tu youtube.py quedo viejo y todavia no
    # tiene `extract_youtubes` (la que combina varios videos), lo EMULAMOS usando
    # `extract_youtube` (uno por uno). Asi el modo YouTube funciona aunque no se
    # haya actualizado ese archivo en tu PC.
    try:
        from .youtube import extract_youtubes
    except ImportError:
        from .youtube import extract_youtube

        def extract_youtubes(yt_urls, timeout=25):
            yt_urls = [u.strip() for u in (yt_urls or []) if u and u.strip()]
            if not yt_urls:
                raise ValueError("No diste ningun enlace de YouTube.")
            if len(yt_urls) == 1:
                return extract_youtube(yt_urls[0], timeout=timeout)
            from .article import Article
            title = ""
            parts: list[str] = []
            errors: list[str] = []
            for u in yt_urls:
                try:
                    art = extract_youtube(u, timeout=timeout)
                    if not title:
                        title = art.title
                    parts.append(art.text)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"- {u}: {exc}")
            if not parts:
                raise ValueError(
                    "No pude leer NINGUNO de los videos de YouTube. Revisa que "
                    "tengan subtitulos. Detalle:\n" + "\n".join(errors)
                )
            return Article(
                url=yt_urls[0], title=title or "Video de YouTube",
                text="\n\n".join(parts),
            )

    cfg = settings
    # `url` puede ser un solo enlace (texto) o varios (lista). Normalizamos.
    urls = url if isinstance(url, list) else [url]
    duration = duration or cfg.video_duration
    voice = voice or cfg.tts_voice
    voice = _resolve_voice(voice)   # si es "automatica", elige una del grupo (rotando)
    rate = rate if rate is not None else cfg.tts_rate
    style = style or cfg.script_style
    cta = cta or cfg.call_to_action
    image_source = (image_source or cfg.image_source or "hybrid").lower()

    if podcast:
        voice_a = _resolve_voice(voice_a or voice)
        voice_b = _resolve_voice(voice_b or cfg.tts_voice)
        voice = voice_a

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = cfg.work_dir / f"job_{stamp}"
    job_dir.mkdir(parents=True, exist_ok=True)
    images_dir = job_dir / "images"

    # 1) Leer los subtitulos del/los video(s) de YouTube y combinarlos
    n = len([u for u in urls if str(u).strip()])
    progress(
        "Leyendo los subtitulos del video de YouTube..." if n <= 1
        else f"Leyendo los subtitulos de {n} videos de YouTube...",
        8,
    )
    article = extract_youtubes(urls)

    # 2) Guion en escenas (mismo motor que el modo noticia)
    progress("Escribiendo el guion viral con IA...", 25)
    script = generate_script(
        article, duration=duration, style=style, cta=cta, n_images=n_images,
        style_instructions=style_instructions,
        podcast=podcast, speaker_a=speaker_a_name, speaker_b=speaker_b_name,
    )
    print(f"[guion] {len(script.scenes)} escenas generadas (desde YouTube)")

    # 3) Voz
    progress("Generando la voz en espanol...", 45)
    audio = synthesize_voice(
        script.narration, voice=voice, rate=rate, out_path=job_dir / "voz.mp3"
    )
    real_duration = probe_duration(audio.audio_path) or audio.duration or float(duration)

    # 4) Medios por escena (fotos o videoclips)
    images = _fetch_media(script.scenes, images_dir, media_type, image_source, progress)
    for im in images:
        print(f"[medios] {im.source}: {im.query[:60]}")

    progress("Listo para revisar imagenes!", 100)

    return PreparedJob(
        job_dir=job_dir,
        title=article.title,
        narration=script.narration,
        scenes=script.scenes,
        images=images,
        audio_path=audio.audio_path,
        audio_words=audio.words,
        real_duration=real_duration,
        titles=script.titles,
        hashtags=script.hashtags,
        image_source=image_source,
        media_type=media_type,
        warning=script.warning,
        voice=voice,
        rate=rate,
        synth_narration=script.narration,
        podcast=podcast,
        voice_a=voice_a,
        voice_b=voice_b,
        speaker_a_name=speaker_a_name,
        speaker_b_name=speaker_b_name,
        style_instructions=style_instructions,
        persona_name=persona_name,
    )


# ==========================================================================
#  MODO HISTORIA - PASO A: crear el BORRADOR (guion + prompts, SIN imagenes)
# ==========================================================================
def draft_story(
    story: str,
    *,
    duration: int | None = None,
    n_images=8,
    voice: str | None = None,
    rate: str | None = None,
    cta: str | None = None,
    image_source: str | None = None,
    media_type: str = "image",
    progress: ProgressFn = _noop,
    style_instructions: str = "",
    persona_name: str = "",
    podcast: bool = False,
    voice_a: str = "",
    voice_b: str = "",
    speaker_a_name: str = "",
    speaker_b_name: str = "",
) -> PreparedJob:
    """
    Convierte la HISTORIA del usuario en un guion dividido en escenas con su
    prompt de imagen, PERO todavia NO genera imagenes ni voz.

    Devuelve un PreparedJob "borrador" para que el usuario revise y edite los
    prompts (y el dialogo) antes de gastar tiempo generando nada.
    """
    cfg = settings
    duration = duration or cfg.video_duration
    voice = _resolve_voice(voice or cfg.tts_voice)
    rate = rate if rate is not None else cfg.tts_rate
    cta = cta or cfg.call_to_action
    image_source = (image_source or cfg.image_source or "hybrid").lower()

    if podcast:
        voice_a = _resolve_voice(voice_a or voice)
        voice_b = _resolve_voice(voice_b or cfg.tts_voice)
        voice = voice_a

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = cfg.work_dir / f"job_{stamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    progress("Escribiendo el guion y los prompts con IA...", 40)
    script = generate_script_from_story(
        story, duration=duration, n_images=n_images, cta=cta,
        style_instructions=style_instructions,
        podcast=podcast, speaker_a=speaker_a_name, speaker_b=speaker_b_name,
    )
    print(f"[historia] {len(script.scenes)} escenas/prompts generados")

    # Titulo amigable: el primero sugerido o las primeras palabras de la historia
    title = (script.titles[0] if script.titles else "").strip()
    if not title:
        title = " ".join(story.strip().split()[:8]) or "Mi historia"

    progress("Borrador listo para revisar!", 100)

    return PreparedJob(
        job_dir=job_dir,
        title=title,
        narration=script.narration,
        scenes=script.scenes,
        images=[],                 # aun no hay imagenes (se generan al aprobar)
        audio_path=None,           # aun no hay voz
        audio_words=[],
        real_duration=float(duration),
        titles=script.titles,
        hashtags=script.hashtags,
        image_source=image_source,
        media_type=media_type,
        warning=script.warning,
        voice=voice,
        rate=rate,
        synth_narration="",
        podcast=podcast,
        voice_a=voice_a,
        voice_b=voice_b,
        speaker_a_name=speaker_a_name,
        speaker_b_name=speaker_b_name,
        style_instructions=style_instructions,
        persona_name=persona_name,
    )


# ==========================================================================
#  Editar el PROMPT de imagen de una escena (en el borrador)
# ==========================================================================
def update_scene_prompt(prepared: PreparedJob, index: int, new_prompt: str) -> None:
    """Cambia la descripcion de imagen (image_prompt) de una escena."""
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    prompt = (new_prompt or "").strip()
    if not prompt:
        raise ValueError("La descripcion de la imagen no puede quedar vacia.")
    # Traducimos a ingles para que luego la busqueda/generacion respete lo pedido.
    english = ensure_english(prompt)
    sc = prepared.scenes[index]
    if english.strip().lower() != (sc.image_prompt or "").strip().lower():
        sc.keyword = english   # refresca la palabra clave de respaldo
    sc.image_prompt = english


# ==========================================================================
#  MODO HISTORIA - PASO B: generar VOZ + IMAGENES desde el borrador aprobado
# ==========================================================================
def prepare_from_draft(
    prepared: PreparedJob,
    *,
    progress: ProgressFn = _noop,
) -> PreparedJob:
    """
    Con los prompts y dialogos ya aprobados por el usuario, genera la VOZ y las
    IMAGENES. Despues el flujo continua igual que el modo noticia (revision de
    imagenes -> ensamblar video final).
    """
    cfg = settings
    job_dir = prepared.job_dir
    images_dir = job_dir / "images"

    narration = prepared.current_narration()

    # 1) Voz
    progress("Generando la voz en espanol...", 35)
    audio = synthesize_voice(
        narration, voice=prepared.voice, rate=prepared.rate, out_path=job_dir / "voz.mp3"
    )
    prepared.audio_path = audio.audio_path
    prepared.audio_words = audio.words
    prepared.real_duration = probe_duration(audio.audio_path) or audio.duration or prepared.real_duration
    prepared.narration = narration
    prepared.synth_narration = narration

    # 2) Medios por escena (fotos o videoclips, segun lo elegido)
    images = _fetch_media(
        prepared.scenes, images_dir, prepared.media_type, prepared.image_source, progress
    )
    prepared.images = images

    progress("Listo para revisar imagenes!", 100)
    return prepared


# ==========================================================================
#  Regenerar / reemplazar la imagen de UNA escena
# ==========================================================================
def regenerate_scene_image(
    prepared: PreparedJob,
    index: int,
    mode: str = "hybrid",
    new_prompt: str | None = None,
    new_keyword: str | None = None,
    attempt: int = 0,
) -> ImageResult:
    """
    Vuelve a generar/buscar la imagen de la escena `index`.

    mode       : "together" | "gemini" | "ai" | "stock" | "hybrid"
    new_prompt : si el usuario edito la descripcion visual, se usa esta
    attempt    : numero de intento (cambia la semilla para obtener algo distinto)
    """
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")

    scene = prepared.scenes[index]
    if new_prompt:
        # Traducimos lo que escribio el usuario a ingles (Pexels y la IA
        # funcionan mejor asi). Esto es lo que hace que el editor SI respete
        # "lloviendo", "carros rojos", etc.
        raw = new_prompt.strip()
        english = ensure_english(raw)
        changed = english.strip().lower() != (scene.image_prompt or "").strip().lower()
        scene.image_prompt = english
        if changed:
            # Si la descripcion cambio, refrescamos tambien la palabra clave de
            # respaldo. Antes se quedaba la vieja (ej. "sunny") y por eso seguia
            # saliendo la misma imagen aunque pidieras otra cosa.
            scene.keyword = english
    if new_keyword:
        scene.keyword = ensure_english(new_keyword.strip())

    images_dir = prepared.job_dir / "images"
    ts = datetime.now().strftime("%H%M%S")

    used = prepared.used_image_urls.setdefault(index, set())
    current = prepared.images[index] if index < len(prepared.images) else None
    if current is not None and getattr(current, "url", ""):
        used.add(current.url)

    # --- Caso VIDEOCLIP: el usuario pidio "otro videoclip" ---
    if (mode or "").lower() == "video":
        dest = images_dir / f"vid_{index:02d}_{ts}_{attempt}.mp4"
        result = fetch_single_video(scene.image_prompt, scene.keyword, dest, used_urls=used)
        if result is None:
            used.clear()
            result = fetch_single_video(scene.image_prompt, scene.keyword, dest, used_urls=used)
        if result is None:
            raise ValueError(
                "No pude encontrar otro videoclip. Prueba con otra descripcion, "
                "o cambia el fondo a 'Fotos'."
            )
        if getattr(result, "url", ""):
            used.add(result.url)
        prepared.images[index] = result
        return result

    # --- Caso FOTO/IMAGEN (comportamiento de siempre) ---
    # nombre nuevo en cada intento (evita que el navegador muestre la imagen vieja en cache)
    dest = images_dir / f"img_{index:02d}_{ts}_{attempt}.jpg"

    seed = 1000 + index * 100 + attempt + 1
    result = fetch_single_image(
        scene.image_prompt, scene.keyword, dest, mode=mode, seed=seed, used_urls=used
    )
    if result is None:
        # Quiza se agotaron las fotos nuevas para esta escena: reiniciamos la
        # memoria y reintentamos (asi vuelve a haber opciones en vez de fallar).
        used.clear()
        result = fetch_single_image(
            scene.image_prompt, scene.keyword, dest, mode=mode, seed=seed, used_urls=used
        )
    if result is None:
        raise ValueError(
            "No pude generar/encontrar una nueva imagen. "
            "Prueba con otra descripcion, o cambia a 'foto real'."
        )

    if getattr(result, "url", ""):
        used.add(result.url)
    prepared.images[index] = result
    return result


def set_scene_image(prepared: PreparedJob, index: int, image_path: Path, source: str = "subida") -> ImageResult:
    """Asigna un archivo ya guardado (imagen O video subido) a una escena."""
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    is_video = Path(image_path).suffix.lower() in (".mp4", ".mov", ".webm", ".m4v")
    result = ImageResult(
        path=Path(image_path), source=source, query="archivo subido", is_video=is_video
    )
    prepared.images[index] = result
    # Si esta escena estaba marcada como "usar audio de mi video", refrescamos la
    # duracion del nuevo video; si ya no es video, desactivamos esa marca.
    scene = prepared.scenes[index]
    if scene.use_own_audio:
        if is_video:
            scene.own_audio_duration = probe_duration(Path(image_path)) or 0.0
        else:
            scene.use_own_audio = False
            scene.own_audio_duration = 0.0
    return result


def set_scene_own_audio(
    prepared: PreparedJob,
    index: int,
    use_own_audio: bool,
    volume: float | None = None,
) -> dict:
    """
    Marca (o desmarca) una escena para que use el AUDIO PROPIO del video subido
    en vez de la voz del avatar (Opcion A: la escena dura lo que dura tu video).

    Solo tiene sentido si la escena tiene un VIDEO como medio. Devuelve un dict
    con el estado resultante (incluida la duracion del video en segundos).
    """
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    scene = prepared.scenes[index]
    img = prepared.images[index] if index < len(prepared.images) else None
    is_video = bool(img and getattr(img, "is_video", False))

    if use_own_audio and not is_video:
        raise ValueError(
            "Para usar el audio propio, esta escena debe tener un VIDEO. "
            "Sube o elige un video en esta escena primero."
        )

    scene.use_own_audio = bool(use_own_audio)
    if volume is not None:
        try:
            scene.own_audio_volume = max(0.0, min(2.0, float(volume)))
        except (TypeError, ValueError):
            pass

    if scene.use_own_audio and img is not None:
        scene.own_audio_duration = round(_effective_video_duration(img), 2)
    elif not scene.use_own_audio:
        scene.own_audio_duration = 0.0

    return {
        "index": index,
        "use_own_audio": scene.use_own_audio,
        "own_audio_volume": scene.own_audio_volume,
        "own_audio_duration": scene.own_audio_duration,
    }


# ==========================================================================
#  Duracion de un video y RECORTE (dejar solo un trozo del clip)
# ==========================================================================
def _media_duration(img: ImageResult | None) -> float:
    """Duracion (seg) del clip original. La cachea en img.duration para no
    volver a medirla en cada revision."""
    if img is None:
        return 0.0
    d = getattr(img, "duration", 0.0) or 0.0
    if d > 0:
        return d
    if getattr(img, "is_video", False):
        d = probe_duration(Path(img.path)) or 0.0
        try:
            img.duration = round(d, 2)
        except Exception:  # noqa: BLE001
            pass
        return d
    return 0.0


def _effective_video_duration(img: ImageResult | None) -> float:
    """
    Cuanto dura el video DESPUES del recorte:
      - si hay trim_end valido: trim_end - trim_start
      - si solo hay trim_start: duracion_original - trim_start
      - si no hay recorte: duracion_original
    """
    if img is None:
        return 0.0
    src = _media_duration(img)
    ts = max(0.0, float(getattr(img, "trim_start", 0.0) or 0.0))
    te = float(getattr(img, "trim_end", 0.0) or 0.0)
    if te and te > ts:
        return round(te - ts, 2)
    if src > 0:
        return round(max(0.5, src - ts), 2)
    return 0.0


def set_scene_trim(prepared: PreparedJob, index: int, start: float, end: float) -> dict:
    """
    Recorta el video de una escena para quedarse SOLO con el trozo [start, end]
    (en segundos). Ej: un clip de 8s del que solo quieres del segundo 4 al 7.

    end=0 (o <=start) significa "hasta el final". Solo aplica a escenas de video.
    """
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    img = prepared.images[index] if index < len(prepared.images) else None
    if not img or not getattr(img, "is_video", False):
        raise ValueError("Solo se pueden recortar escenas que tienen un VIDEO.")

    src = _media_duration(img)
    try:
        start = max(0.0, float(start))
    except (TypeError, ValueError):
        start = 0.0
    try:
        end = float(end or 0.0)
    except (TypeError, ValueError):
        end = 0.0

    # Limitamos a la duracion real del clip (si la conocemos).
    if src > 0:
        start = min(start, max(0.0, src - 0.3))
        if end and end > src:
            end = src
    if end and end <= start:
        end = 0.0  # rango invalido -> hasta el final

    img.trim_start = round(start, 2)
    img.trim_end = round(end, 2)

    # Si la escena usa el audio del video, su duracion ahora es la del recorte.
    scene = prepared.scenes[index]
    if scene.use_own_audio:
        scene.own_audio_duration = round(_effective_video_duration(img), 2)

    return {
        "index": index,
        "trim_start": img.trim_start,
        "trim_end": img.trim_end,
        "media_duration": round(src, 2),
        "effective_duration": _effective_video_duration(img),
    }


# ==========================================================================
#  VARIOS PEDAZOS en una escena (mini-clips que se muestran uno tras otro)
# ==========================================================================
def _clip_from_image(img: ImageResult) -> dict:
    """Crea una 'pieza' a partir del fondo actual de la escena (para arrancar
    la lista de pedazos con lo que ya habia)."""
    return {
        "path": str(img.path),
        "file": Path(img.path).name,
        "is_video": bool(getattr(img, "is_video", False)),
        "seconds": 4.0,   # peso/duracion aprox. del fondo principal
        "trim_start": float(getattr(img, "trim_start", 0.0) or 0.0),
        "trim_end": float(getattr(img, "trim_end", 0.0) or 0.0),
        "source": getattr(img, "source", "fondo"),
    }


def add_scene_clip(
    prepared: PreparedJob,
    index: int,
    file_path: Path,
    is_video: bool,
    seconds: float = 2.0,
    source: str = "subida",
    position: int | None = None,
) -> list:
    """
    Agrega un PEDAZO (mini-clip o imagen) a una escena. La primera vez, la lista
    se inicia con el fondo actual como pieza 1, y luego se agrega el pedazo nuevo.
    Asi puedes tener: [fondo 4s] + [meme 2s] + [foto 2s] dentro de una escena.
    """
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    scene = prepared.scenes[index]
    if not scene.clips:
        img = prepared.images[index] if index < len(prepared.images) else None
        scene.clips = [_clip_from_image(img)] if img is not None else []
    new = {
        "path": str(file_path),
        "file": Path(file_path).name,
        "is_video": bool(is_video),
        "seconds": max(0.3, float(seconds or 2.0)),
        "trim_start": 0.0,
        "trim_end": 0.0,
        "source": source,
    }
    if position is None or position < 0 or position > len(scene.clips):
        scene.clips.append(new)
    else:
        scene.clips.insert(position, new)
    return scene.clips


def remove_scene_clip(prepared: PreparedJob, index: int, clip_index: int) -> list:
    """Quita un pedazo de la escena. Si no queda ninguno, la escena vuelve a su
    fondo unico normal (clips vacio)."""
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    scene = prepared.scenes[index]
    if scene.clips and 0 <= clip_index < len(scene.clips):
        scene.clips.pop(clip_index)
    if not scene.clips:
        scene.clips = []
    return scene.clips


def set_scene_clip_seconds(prepared: PreparedJob, index: int, clip_index: int, seconds: float) -> list:
    """Cambia los segundos (aprox.) de un pedazo dentro de la escena."""
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    scene = prepared.scenes[index]
    if scene.clips and 0 <= clip_index < len(scene.clips):
        try:
            scene.clips[clip_index]["seconds"] = max(0.3, float(seconds))
        except (TypeError, ValueError):
            pass
    return scene.clips


def _flatten_media(
    prepared: PreparedJob, img_durations: list[float]
) -> tuple[list[Path], list[float], list[bool], list[tuple[float, float]]]:
    """
    Convierte las escenas en una lista PLANA de piezas visuales para el
    ensamblaje. Una escena SIN pedazos aporta 1 pieza (su fondo, con la duracion
    de la escena). Una escena CON pedazos aporta N piezas cuyas duraciones se
    reparten (proporcional a sus 'seconds') dentro de la duracion de la escena,
    para que el total de la escena NO cambie y todo siga sincronizado con la voz.
    """
    paths: list[Path] = []
    durs: list[float] = []
    isvid: list[bool] = []
    trims: list[tuple[float, float]] = []
    for i, scene in enumerate(prepared.scenes):
        D = img_durations[i] if i < len(img_durations) else 0.0
        clips = getattr(scene, "clips", None)
        if clips:
            weights = [max(0.1, float(c.get("seconds", 0) or 0)) for c in clips]
            tot = sum(weights) or 1.0
            for c, w in zip(clips, weights):
                paths.append(Path(c["path"]))
                durs.append(D * w / tot)
                isvid.append(bool(c.get("is_video")))
                trims.append((float(c.get("trim_start", 0) or 0), float(c.get("trim_end", 0) or 0)))
        else:
            im = prepared.images[i] if i < len(prepared.images) else None
            if im is None:
                continue
            paths.append(Path(im.path))
            durs.append(D)
            isvid.append(bool(getattr(im, "is_video", False)))
            trims.append((float(getattr(im, "trim_start", 0) or 0), float(getattr(im, "trim_end", 0) or 0)))
    return paths, durs, isvid, trims


# ==========================================================================
#  Editar el DIALOGO (texto narrado) de una escena
# ==========================================================================
def update_scene_text(prepared: PreparedJob, index: int, new_text: str) -> None:
    """
    Cambia el dialogo (lo que se narra) de una escena.

    OJO: al cambiar el dialogo, la voz y los subtitulos quedaran desactualizados.
    Por eso 'assemble_prepared' detecta el cambio y REGENERA la voz automaticamente
    antes de armar el video, para que todo quede sincronizado.
    """
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    text = (new_text or "").strip()
    if not text:
        raise ValueError("El dialogo no puede quedar vacio. Si no la quieres, elimina la escena.")
    prepared.scenes[index].text = text
    prepared.narration = prepared.current_narration()


# ==========================================================================
#  Eliminar una escena completa (su imagen + su dialogo)
# ==========================================================================
def delete_scene(prepared: PreparedJob, index: int) -> None:
    """Quita por completo una escena (imagen y dialogo) del video."""
    if index < 0 or index >= len(prepared.scenes):
        raise ValueError("Escena fuera de rango.")
    if len(prepared.scenes) <= 1:
        raise ValueError("No puedes eliminar la unica escena que queda.")
    prepared.scenes.pop(index)
    if index < len(prepared.images):
        prepared.images.pop(index)
    prepared.narration = prepared.current_narration()


# ==========================================================================
#  Agregar una escena NUEVA (su dialogo + su imagen/video)
# ==========================================================================
def add_scene(
    prepared: PreparedJob,
    text: str,
    image_desc: str | None = None,
    position: int | None = None,
) -> ImageResult:
    """
    Agrega una escena nueva al video que se esta revisando.

    - text       : el dialogo que se va a narrar (en espanol).
    - image_desc : que imagen/video se quiere (puede escribirse en espanol; se
                   traduce a ingles). Si va vacio, se deduce del propio dialogo.
    - position   : indice donde insertarla (0 = al inicio). Si es None o invalido,
                   se agrega al FINAL.

    Genera de una vez la imagen/video de la escena para que aparezca en la
    revision. La voz se regenera sola al armar el video (porque cambia la
    narracion). Devuelve el ImageResult de la nueva escena.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("El dialogo de la escena nueva no puede quedar vacio.")

    # Que imagen quiere (traducida a ingles para que la busqueda/IA la respete)
    desc = (image_desc or "").strip() or text
    english = ensure_english(desc)
    scene = Scene(text=text, image_prompt=english, keyword=english)

    # Donde insertarla
    n = len(prepared.scenes)
    if position is None or not isinstance(position, int) or position < 0 or position > n:
        pos = n
    else:
        pos = position

    # Conseguimos su imagen/video ANTES de insertarla (si falla, no dejamos una
    # escena sin medio).
    images_dir = prepared.job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    mt = (prepared.media_type or "image").lower()

    result: ImageResult | None = None
    if mt in ("video", "mixed"):
        dest = images_dir / f"vid_new_{ts}.mp4"
        result = fetch_single_video(scene.image_prompt, scene.keyword, dest, used_urls=set())
        if result is None:
            dest = images_dir / f"img_new_{ts}.jpg"
            result = fetch_single_image(
                scene.image_prompt, scene.keyword, dest, mode="stock", seed=4321, used_urls=set()
            )
    else:
        dest = images_dir / f"img_new_{ts}.jpg"
        result = fetch_single_image(
            scene.image_prompt, scene.keyword, dest,
            mode=prepared.image_source, seed=4321, used_urls=set(),
        )

    if result is None:
        raise ValueError(
            "No pude conseguir imagen/video para la escena nueva. "
            "Prueba con otra descripcion."
        )

    # Insertamos la escena y su medio en la misma posicion
    prepared.scenes.insert(pos, scene)
    if pos <= len(prepared.images):
        prepared.images.insert(pos, result)
    else:
        prepared.images.append(result)

    prepared.narration = prepared.current_narration()
    # Los indices de las escenas cambiaron: reiniciamos la memoria de fotos ya
    # vistas (esta guardada por indice) para que no se desincronice.
    prepared.used_image_urls = {}
    return result


# ==========================================================================
#  Construir la pista de AUDIO por ESCENA (podcast y/o video con audio propio)
# ==========================================================================
def _needs_per_scene_audio(prepared: PreparedJob) -> bool:
    """
    Decide si hay que armar el audio ESCENA POR ESCENA en vez de una sola pista.
    Es necesario cuando:
      - Es modo PODCAST (cada escena puede tener voz distinta), o
      - Alguna escena usa el AUDIO PROPIO de su video (Opcion A).
    """
    if prepared.podcast:
        return True
    return any(getattr(s, "use_own_audio", False) for s in prepared.scenes)


def _build_scene_audio_timeline(
    prepared: PreparedJob,
    progress: ProgressFn = _noop,
) -> tuple[Path, list[WordTiming], list[float]]:
    """
    Genera un SEGMENTO de audio por cada escena y los une en una sola pista:
      - Escena normal (avatar): se sintetiza su texto con su voz (la de podcast
        A/B o la voz unica). Sus tiempos de palabra se DESPLAZAN por el tiempo
        acumulado, para que los subtitulos queden sincronizados.
      - Escena con audio propio (video): se extrae el audio del video subido, a
        su volumen elegido, y la escena dura lo que dura el video. Esa escena NO
        lleva subtitulos de voz (porque habla el video, no el avatar).

    Devuelve: (ruta_audio_final, palabras_con_tiempos, duracion_por_escena).
    """
    job_dir = prepared.job_dir
    seg_dir = job_dir / "audio_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    segments: list[Path] = []
    combined_words: list[WordTiming] = []
    per_scene_durations: list[float] = []
    cursor = 0.0
    total = len(prepared.scenes)

    for i, scene in enumerate(prepared.scenes):
        progress(f"Preparando audio de la escena {i + 1} de {total}...", 15 + int(20 * (i / max(1, total))))
        img = prepared.images[i] if i < len(prepared.images) else None
        is_video = bool(img and getattr(img, "is_video", False))
        seg_wav = seg_dir / f"seg_{i:02d}.wav"

        # --- Escena con AUDIO PROPIO del video (Opcion A) ---
        if scene.use_own_audio and is_video:
            t_start = max(0.0, float(getattr(img, "trim_start", 0.0) or 0.0))
            dur = _effective_video_duration(img) or scene.own_audio_duration or 3.0
            if has_audio_stream(Path(img.path)):
                extract_audio(
                    Path(img.path), seg_wav,
                    volume=scene.own_audio_volume, duration=dur, start=t_start,
                )
            else:
                # El video no trae sonido: ponemos silencio para respetar su duracion.
                make_silence(dur, seg_wav)
            scene.own_audio_duration = round(dur, 2)
            segments.append(seg_wav)
            per_scene_durations.append(dur)
            cursor += dur
            continue

        # --- Escena normal: voz del avatar (TTS) ---
        voice = voice_for_scene(prepared, scene)
        mp3 = seg_dir / f"seg_{i:02d}.mp3"
        audio = synthesize_voice(scene.text, voice=voice, rate=prepared.rate, out_path=mp3)
        words = audio.words

        if words:
            # IMPORTANTE (sincronia de subtitulos): Edge TTS suele dejar un
            # pequeno SILENCIO al inicio de cada clip. Si no lo quitamos, en el
            # modo podcast/audio-por-escena el habla queda desplazada respecto a
            # los tiempos de palabra y los subtitulos se sienten "atrasados",
            # peor mientras mas escenas hay. Solucion: RECORTAMOS el silencio
            # inicial (dejando un respiro minimo) y el sobrante final, y
            # desplazamos los tiempos de palabra para que el habla empiece justo
            # al inicio del segmento. Asi cada escena queda perfectamente pegada
            # a su subtitulo, sin desfase acumulado.
            lead_in = 0.05  # respiro minimo antes de la primera palabra
            tail = 0.15     # colita despues de la ultima palabra (no cortar)
            offset = max(0.0, words[0].start - lead_in)
            seg_end = words[-1].end + tail
            trim_and_format_audio(audio.audio_path, seg_wav, start=offset, end=seg_end)
            for w in words:
                combined_words.append(
                    WordTiming(
                        word=w.word,
                        start=round((w.start - offset) + cursor, 3),
                        end=round((w.end - offset) + cursor, 3),
                    )
                )
        else:
            # Sin tiempos de palabra (raro): dejamos el audio tal cual.
            normalize_audio(audio.audio_path, seg_wav)

        dur = probe_duration(seg_wav) or (audio.duration if not words else 1.0) or 1.0
        segments.append(seg_wav)
        per_scene_durations.append(dur)
        cursor += dur

    progress("Uniendo el audio de todas las escenas...", 36)
    final_audio = concat_audio(segments, job_dir / "voz.mp3")
    return final_audio, combined_words, per_scene_durations


# ==========================================================================
#  PASO 2: ensamblar el video final con las imagenes ya aprobadas
# ==========================================================================
def assemble_prepared(
    prepared: PreparedJob,
    *,
    subtitle_color: str = "amarillo",
    subtitle_position: str = "center",
    use_avatar: bool = False,
    voice: str | None = None,
    music_mode: str = "auto",
    music_volume: float = 0.15,
    aspect: str = "9:16",
    progress: ProgressFn = _noop,
) -> VideoJobResult:
    cfg = settings
    job_dir = prepared.job_dir

    # Formato del video (9:16 vertical, 16:9 horizontal, 1:1 cuadrado)
    video_w, video_h = resolution_for(aspect)

    # ¿El usuario eligio una voz distinta en la pantalla de revision?
    # (puede ser "hombre", "mujer", "automatica" o un nombre de voz concreto)
    desired_voice = _resolve_voice(voice) if voice else None
    voice_changed = desired_voice is not None and desired_voice != prepared.voice

    # Duraciones por escena; si el flujo por escena las define, las usamos.
    per_scene_img_durations: list[float] | None = None

    if _needs_per_scene_audio(prepared):
        # --- FLUJO POR ESCENA (podcast y/o video con audio propio) ---
        # Aqui cada escena tiene su propio segmento de audio (voz A/B, o el audio
        # del video subido) y los unimos en una sola pista, con los subtitulos
        # sincronizados por escena.
        if voice_changed and not prepared.podcast:
            prepared.voice = desired_voice  # type: ignore[assignment]
            print(f"[voz] el usuario cambio la voz -> {prepared.voice}")
        print("[audio] armando pista ESCENA POR ESCENA (podcast/audio propio)")
        final_audio, combined_words, per_scene_img_durations = _build_scene_audio_timeline(
            prepared, progress=progress
        )
        prepared.audio_path = final_audio
        prepared.audio_words = combined_words
        prepared.real_duration = probe_duration(final_audio) or sum(per_scene_img_durations) or prepared.real_duration
        prepared.narration = prepared.current_narration()
        prepared.synth_narration = prepared.narration
    else:
        # --- FLUJO NORMAL (una sola pista de voz continua) ---
        # Si el usuario edito dialogos o elimino escenas, la narracion cambio:
        # regeneramos la VOZ para que el audio y los subtitulos queden sincronizados.
        current = prepared.current_narration()
        narration_changed = bool(current) and current != prepared.synth_narration

        if voice_changed or narration_changed or prepared.audio_path is None:
            if voice_changed:
                prepared.voice = desired_voice  # type: ignore[assignment]
                print(f"[voz] el usuario cambio la voz -> {prepared.voice}")
            # Texto a narrar: el actual si cambio; si no, el mismo de antes.
            text_for_voice = current if narration_changed else (prepared.synth_narration or current)
            if not text_for_voice:
                text_for_voice = prepared.narration
            progress("Regenerando la voz...", 15)
            print("[voz] generando audio y tiempos")
            audio = synthesize_voice(
                text_for_voice, voice=prepared.voice, rate=prepared.rate, out_path=job_dir / "voz.mp3"
            )
            prepared.audio_path = audio.audio_path
            prepared.audio_words = audio.words
            prepared.real_duration = probe_duration(audio.audio_path) or audio.duration or prepared.real_duration
            prepared.narration = text_for_voice
            prepared.synth_narration = text_for_voice

    # Subtitulos
    progress("Creando los subtitulos sincronizados...", 30)
    sub_style = SubtitleStyle(
        name=subtitle_color, position=subtitle_position, lead_sec=cfg.subtitle_lead
    )
    if prepared.audio_words:
        print(f"[subtitulos] {len(prepared.audio_words)} palabras con tiempos exactos")
        subs = build_ass_subtitles(
            prepared.audio_words, job_dir / "subtitles.ass", style=sub_style,
            video_w=video_w, video_h=video_h,
        )
    else:
        print("[subtitulos] usando Plan B (reparto por texto)")
        subs = build_subtitles_from_text(
            prepared.narration, prepared.real_duration, job_dir / "subtitles.ass",
            style=sub_style, video_w=video_w, video_h=video_h,
        )

    # Avatar opcional
    avatar_video = None
    if use_avatar:
        progress("Generando el avatar en la nube...", 55)
        face = _pick_avatar_face(cfg.assets_dir, prepared.voice)
        print(f"[avatar] usando foto: {face.name}")
        avatar_video = avatar_mod.generate_avatar_video(
            prepared.audio_path, face, job_dir / "avatar.mp4"
        )

    # Duraciones sincronizadas por escena
    if per_scene_img_durations is not None and len(per_scene_img_durations) == len(prepared.images):
        # El flujo por escena ya calculo la duracion EXACTA de cada escena
        # (incluidas las de video con audio propio).
        img_durations = per_scene_img_durations
    else:
        img_durations = _scene_durations(prepared.scenes, prepared.real_duration)
        if len(img_durations) != len(prepared.images):
            img_durations = [prepared.real_duration / max(1, len(prepared.images))] * len(prepared.images)

    # Musica de fondo segun el modo elegido:
    #   "off"  -> sin musica
    #   "own"  -> la que subio el usuario (si no hay, cae a automatica)
    #   "auto" -> una pista automatica generada (100% libre de derechos)
    mode = (music_mode or "auto").lower()
    music_file: Path | None = None
    if mode == "off":
        music_file = None
    elif mode == "own" and prepared.music_path and Path(prepared.music_path).exists():
        music_file = Path(prepared.music_path)
    else:
        music_file = None
        if music_mod is not None:
            progress("Preparando la musica de fondo...", 70)
            try:
                music_file = music_mod.pick_auto_music()
            except Exception as exc:  # noqa: BLE001
                print(f"[musica] no disponible: {exc}")
                music_file = None

    # Ensamblar
    progress("Ensamblando el video final...", 75)
    logo = cfg.assets_dir / "logo.png"
    out_name = f"{prepared.job_dir.name}_{_slugify(prepared.title)}.mp4"
    out_path = cfg.output_dir / out_name
    # Marca, por escena, si su fondo es un videoclip (para que el ensamblaje
    # lo trate como video en vez de aplicarle el zoom de fotos).
    # Aplanamos las escenas en piezas visuales. Una escena puede tener VARIOS
    # pedazos (mini-clips) que se muestran uno tras otro dentro de su tiempo.
    flat_paths, flat_durs, flat_isvid, flat_trims = _flatten_media(prepared, img_durations)
    result = build_video(
        images=flat_paths,
        audio_path=prepared.audio_path,
        subtitles_path=subs,
        out_path=out_path,
        work_dir=job_dir,
        logo_path=logo if logo.exists() else None,
        avatar_video=avatar_video,
        target_duration=prepared.real_duration,
        image_durations=flat_durs,
        music_path=music_file,
        music_volume=music_volume,
        resolution=(video_w, video_h),
        media_is_video=flat_isvid,
        media_trims=flat_trims,
    )

    progress("Listo!", 100)
    return VideoJobResult(
        video_path=result.video_path,
        title=prepared.title,
        narration=prepared.narration,
        titles=prepared.titles,
        hashtags=prepared.hashtags,
        duration=result.duration,
        used_avatar=bool(avatar_video),
        image_source=prepared.image_source,
    )


# ==========================================================================
#  Compatibilidad: flujo de un solo paso (sin revision de imagenes)
# ==========================================================================
def create_video_from_url(
    url: str,
    *,
    duration: int | None = None,
    style: str | None = None,
    voice: str | None = None,
    rate: str | None = None,
    cta: str | None = None,
    subtitle_color: str = "amarillo",
    subtitle_position: str = "center",
    use_avatar: bool | None = None,
    image_source: str | None = None,
    progress: ProgressFn = _noop,
) -> VideoJobResult:
    prepared = prepare_video(
        url,
        duration=duration,
        style=style,
        voice=voice,
        rate=rate,
        cta=cta,
        image_source=image_source,
        progress=progress,
    )
    return assemble_prepared(
        prepared,
        subtitle_color=subtitle_color,
        subtitle_position=subtitle_position,
        use_avatar=bool(use_avatar) if use_avatar is not None else settings.avatar_enabled,
        progress=progress,
    )
