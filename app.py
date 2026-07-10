"""
ViroFeed AI Personal - Servidor web local (interfaz)

Flujo en DOS PASOS (como el editor de ViroFeed):
  1) PREPARAR: genera guion + voz + imagenes y te las muestra para revisar.
  2) REVISAR : cambias/regeneras las imagenes que salieron mal.
  3) GENERAR : arma el video final con las imagenes aprobadas.

Para arrancar:   python app.py
Luego abre:      http://localhost:5000
"""
from __future__ import annotations

import json
import re
import sys
import threading
import traceback
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename


# --------------------------------------------------------------------------
#  AUTO-REPARACION: si falta algun archivo nuevo del programa (porque el
#  actualizar.bat viejo no lo trajo), lo descargamos solos desde GitHub ANTES
#  de importar el resto. Asi el programa nunca se queda sin abrir por un
#  archivo faltante.
# --------------------------------------------------------------------------
_RAW_BASE = "https://raw.githubusercontent.com/MARK-DUTY/VIROFEED-PERSONAL/main"
# Archivos que deben existir y, si aplica, CONTENER cierta funcion nueva.
# Si el archivo falta O quedo viejo (no tiene esa funcion), lo volvemos a bajar.
# Asi, si a alguien se le quedo un archivo viejo, el programa se auto-repara solo.
_REQUIRED_FILES = {
    "pipeline/music.py": None,
    "pipeline/youtube.py": "def extract_youtubes",
}


def _self_repair() -> None:
    import urllib.request
    here = Path(__file__).resolve().parent
    for rel, marker in _REQUIRED_FILES.items():
        dest = here / rel
        needs = not dest.exists()
        if not needs and marker:
            try:
                needs = marker not in dest.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                needs = True
        if not needs:
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"[auto-reparacion] actualizando {rel} desde GitHub...")
            urllib.request.urlretrieve(f"{_RAW_BASE}/{rel}", str(dest))
            print(f"[auto-reparacion] listo: {rel}")
        except Exception as exc:  # noqa: BLE001
            print(f"[auto-reparacion] no pude descargar {rel}: {exc}")


_self_repair()

from pipeline.config import settings
from pipeline.runner import (
    _media_duration as media_duration,
    add_scene,
    add_scene_clip,
    remove_scene_clip,
    set_scene_clip_seconds,
    assemble_prepared,
    delete_scene,
    draft_story,
    planned_scene_durations,
    prepare_from_draft,
    prepare_video,
    prepare_youtube,
    regenerate_scene_image,
    set_scene_image,
    set_scene_own_audio,
    set_scene_trim,
    update_scene_prompt,
    update_scene_text,
    voice_for_scene,
)
from pipeline.voice import (
    foreign_accent_options,
    list_spanish_voices,
    synthesize_scene_preview,
    synthesize_voice_sample,
)

app = Flask(__name__)


# ==========================================================================
#  AVATARES / PERSONAJES (antes en pipeline/personas.py, ahora AQUI dentro).
#  Se movio a app.py a proposito: el actualizar.bat viejo baja una lista fija
#  de archivos que NO incluye personas.py, y descargarlo aparte fallaba por el
#  limite de GitHub (429). Como app.py SIEMPRE se descarga, aqui nunca falta.
#
#  Un "avatar" es una PERSONALIDAD guardada: nombre + voz (que define el acento
#  por pais) + estilo de hablar (serio, chismoso, galan...). El estilo cambia
#  COMO ESCRIBE la IA el guion; el acento lo pone la voz elegida.
# ==========================================================================
STYLE_PRESETS: dict[str, dict] = {
    "neutral": {"label": "Normal / neutral", "instructions": ""},
    "serio_noticiero": {
        "label": "Noticiero serio (formal)",
        "instructions": (
            "Escribe con un tono FORMAL, serio y profesional, como un presentador "
            "de noticiero nocturno de television. Frases claras y con autoridad, "
            "vocabulario correcto, sin bromas ni palabras coloquiales. Transmite "
            "credibilidad y seriedad."
        ),
    },
    "comico": {
        "label": "Comico / relajiento",
        "instructions": (
            "Escribe con MUCHO humor, ocurrente y exagerado, como un personaje de "
            "comedia de television mexicana. Usa expresiones chistosas, doble "
            "sentido ligero (sin groserias) y comentarios divertidos, pero sin "
            "perder el hilo de lo que se cuenta. Que de risa y sea muy expresivo."
        ),
    },
    "espectaculos": {
        "label": "Espectaculos / farandula",
        "instructions": (
            "Escribe con el tono animado y chismoso de un programa de espectaculos "
            "y farandula. Muy emocionado, curioso, con exclamaciones y frases de "
            "'no lo vas a creer'. Genera intriga y mantiene la atencion como en un "
            "programa de chismes de la tele."
        ),
    },
    "chismosa": {
        "label": "Vecina chismosa",
        "instructions": (
            "Escribe como una vecina chismosa contando el chisme del barrio: "
            "confianzuda, exagerada, curiosa y con mucho drama. Usa expresiones de "
            "'ay comadre', 'no me lo vas a creer', 'te cuento'. Muy coloquial y "
            "entretenida, como platicando en la esquina."
        ),
    },
    "galan": {
        "label": "Galan presumido",
        "instructions": (
            "Escribe como un galan presumido, coqueto y muy seguro de si mismo. "
            "Tono seductor y confiado, se echa flores, habla con actitud de "
            "conquistador simpatico (sin faltar al respeto). Que suene carismatico "
            "y un poco payaso."
        ),
    },
    "motivador": {
        "label": "Motivador / coach",
        "instructions": (
            "Escribe con energia positiva y motivadora, como un coach que inspira. "
            "Frases que animan, con fuerza y entusiasmo, que dejan al espectador "
            "con ganas de actuar."
        ),
    },
    "dramatico": {
        "label": "Dramatico / suspenso",
        "instructions": (
            "Escribe con tono dramatico y de suspenso, como narrador de historias "
            "de misterio. Crea tension, pausas de intriga y un final que sorprenda."
        ),
    },
}

DEFAULT_STYLE = "neutral"

_PERSONA_ACCENTS: dict[str, str] = {
    "es-MX": "Mexico", "es-ES": "Espana", "es-AR": "Argentina",
    "es-CO": "Colombia", "es-US": "Estados Unidos", "es-CL": "Chile",
    "es-PE": "Peru", "es-VE": "Venezuela", "es-EC": "Ecuador",
    "es-GT": "Guatemala", "es-CR": "Costa Rica", "es-PA": "Panama",
    "es-DO": "Rep. Dominicana", "es-UY": "Uruguay", "es-PY": "Paraguay",
    "es-BO": "Bolivia", "es-SV": "El Salvador", "es-HN": "Honduras",
    "es-NI": "Nicaragua", "es-PR": "Puerto Rico", "es-CU": "Cuba",
    "es-GQ": "Guinea Ecuatorial",
}

_PERSONA_FEMALE_NAMES = {
    "dalia", "elvira", "salome", "paloma", "larissa", "ximena", "sabina",
    "tania", "marisol", "yolanda", "nuria", "renata", "emilia", "julia",
    "camila", "valentina", "abril", "luciana", "catalina", "amanda",
    "estrella", "vera", "marta", "irene", "xiaoxiao", "sunhi", "nanami",
    "jenny", "denise", "elsa", "katja", "francisca",
}

_PERSONAS_LOCK = threading.Lock()


def style_options() -> list[dict]:
    """Lista de estilos para el menu de la interfaz."""
    return [{"value": k, "label": v["label"]} for k, v in STYLE_PRESETS.items()]


def style_instructions_for(style: str, custom_style: str = "") -> str:
    """Instrucciones de TONO para inyectar en el prompt de la IA."""
    if (style or "").strip().lower() == "custom":
        return (custom_style or "").strip()
    preset = STYLE_PRESETS.get((style or "").strip().lower())
    return preset["instructions"] if preset else ""


def _persona_country_for_voice(voice: str) -> str:
    locale = "-".join((voice or "").split("-")[:2])
    return _PERSONA_ACCENTS.get(locale, locale or "Espanol")


def _persona_looks_female(voice: str) -> bool:
    name = (voice or "").lower()
    return any(fn in name for fn in _PERSONA_FEMALE_NAMES)


def _personas_store_path() -> Path:
    return settings.work_dir / "avatars.json"


def _personas_load_all() -> list[dict]:
    path = _personas_store_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:  # noqa: BLE001
        pass
    return []


def _personas_save_all(items: list[dict]) -> None:
    path = _personas_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _persona_clean(persona: dict) -> dict:
    name = (persona.get("name") or "").strip() or "Avatar sin nombre"
    voice = (persona.get("voice") or "").strip() or settings.tts_voice
    style = (persona.get("style") or DEFAULT_STYLE).strip()
    custom_style = (persona.get("custom_style") or "").strip()
    gender = (persona.get("gender") or "").strip().lower()
    if gender not in ("hombre", "mujer"):
        gender = "mujer" if _persona_looks_female(voice) else "hombre"
    return {
        "id": persona.get("id") or uuid.uuid4().hex[:12],
        "name": name,
        "voice": voice,
        "style": style,
        "custom_style": custom_style,
        "gender": gender,
        "accent": _persona_country_for_voice(voice),
    }


def list_personas() -> list[dict]:
    with _PERSONAS_LOCK:
        return [_persona_clean(p) for p in _personas_load_all()]


def get_persona(persona_id: str) -> dict | None:
    if not persona_id:
        return None
    for p in list_personas():
        if p["id"] == persona_id:
            return p
    return None


def create_persona(persona: dict) -> dict:
    with _PERSONAS_LOCK:
        items = _personas_load_all()
        new = _persona_clean({**persona, "id": None})
        items.append(new)
        _personas_save_all(items)
        return new


def update_persona(persona_id: str, persona: dict) -> dict:
    with _PERSONAS_LOCK:
        items = _personas_load_all()
        for i, p in enumerate(items):
            if (p.get("id") or "") == persona_id:
                merged = _persona_clean({**p, **persona, "id": persona_id})
                items[i] = merged
                _personas_save_all(items)
                return merged
    raise ValueError("No encontre ese avatar para actualizar.")


def delete_persona(persona_id: str) -> bool:
    with _PERSONAS_LOCK:
        items = _personas_load_all()
        remaining = [p for p in items if (p.get("id") or "") != persona_id]
        if len(remaining) == len(items):
            return False
        _personas_save_all(remaining)
        return True


# `personas_mod` apunta a ESTE mismo modulo, para que el resto del codigo pueda
# seguir llamando `personas_mod.list_personas()`, etc., sin cambios.
personas_mod = sys.modules[__name__]


# Nombres de pais por codigo de idioma, para mostrar voces de forma amigable
# (ej: "es-MX-DaliaNeural" -> "Mexico"). Asi el usuario ubica rapido la voz.
_ES_COUNTRIES = {
    "es-MX": "Mexico", "es-ES": "Espana", "es-AR": "Argentina",
    "es-CO": "Colombia", "es-US": "Estados Unidos", "es-CL": "Chile",
    "es-PE": "Peru", "es-VE": "Venezuela", "es-EC": "Ecuador",
    "es-GT": "Guatemala", "es-CR": "Costa Rica", "es-PA": "Panama",
    "es-DO": "Rep. Dominicana", "es-UY": "Uruguay", "es-PY": "Paraguay",
    "es-BO": "Bolivia", "es-SV": "El Salvador", "es-HN": "Honduras",
    "es-NI": "Nicaragua", "es-PR": "Puerto Rico", "es-CU": "Cuba",
    "es-GQ": "Guinea Ecuatorial",
}

# Atajos de genero -> voz concreta (para el preview cuando el usuario tiene
# elegida una opcion generica como "automatica", "hombre" o "mujer").
_PREVIEW_MALE = "es-MX-JorgeNeural"
_PREVIEW_FEMALE = "es-MX-DaliaNeural"
_GENERIC_VOICE = {
    "": _PREVIEW_MALE, "random": _PREVIEW_MALE, "auto": _PREVIEW_MALE,
    "automatica": _PREVIEW_MALE, "automática": _PREVIEW_MALE,
    "aleatoria": _PREVIEW_MALE, "azar": _PREVIEW_MALE,
    "hombre": _PREVIEW_MALE, "masculino": _PREVIEW_MALE,
    "mujer": _PREVIEW_FEMALE, "femenino": _PREVIEW_FEMALE,
}


def _voice_options() -> list[dict]:
    """
    Lista de voces en espanol con una etiqueta amigable para el menu:
      {"value": "es-MX-DaliaNeural", "label": "es-MX-DaliaNeural - Mexico - Mujer"}
    Asi el usuario reconoce de que pais es y si es hombre o mujer.
    """
    options = []
    for v in list_spanish_voices():
        short = v.get("ShortName")
        if not short:
            continue
        locale = v.get("Locale", "")
        country = _ES_COUNTRIES.get(locale, locale or "Espanol")
        gender = "Mujer" if str(v.get("Gender", "")).lower().startswith("f") else "Hombre"
        options.append({"value": short, "label": f"{short}  ·  {country}  ·  {gender}"})
    # Ordenamos: primero Mexico, luego Espana, luego el resto (alfabetico).
    def _rank(opt):
        val = opt["value"]
        if val.startswith("es-MX"):
            return (0, val)
        if val.startswith("es-ES"):
            return (1, val)
        return (2, val)
    options.sort(key=_rank)
    return options


def _resolve_preview_voice(voice: str) -> str:
    """Convierte una eleccion generica (automatica/hombre/mujer) en una voz
    concreta para poder generar la muestra. Si ya es un nombre concreto, lo deja."""
    key = (voice or "").strip().lower()
    return _GENERIC_VOICE.get(key, voice.strip())


def _resolve_persona_options(data: dict) -> dict:
    """
    A partir de lo que eligio el usuario (avatar guardado, estilo, o modo
    podcast con dos avatares/voces), arma los parametros que necesitan las
    funciones del pipeline:

      - style_instructions, persona_name   (narrador unico)
      - podcast, voice_a, voice_b, speaker_a_name, speaker_b_name  (modo podcast)
      - voice_override: si se eligio un avatar, su voz manda sobre el menu "Voz".

    Acepta en `data`:
      avatar_id, style_key, podcast, avatar_a_id, avatar_b_id, voice_a, voice_b,
      speaker_a_name, speaker_b_name
    """
    out: dict = {
        "style_instructions": "",
        "persona_name": "",
        "podcast": False,
        "voice_a": "",
        "voice_b": "",
        "speaker_a_name": "",
        "speaker_b_name": "",
        "voice_override": "",
    }

    podcast = bool(data.get("podcast"))

    if podcast:
        out["podcast"] = True
        pa = personas_mod.get_persona(data.get("avatar_a_id") or "")
        pb = personas_mod.get_persona(data.get("avatar_b_id") or "")

        if pa:
            out["voice_a"] = pa["voice"]
            out["speaker_a_name"] = pa["name"]
            style_a = personas_mod.style_instructions_for(pa["style"], pa.get("custom_style", ""))
        else:
            out["voice_a"] = (data.get("voice_a") or "").strip()
            out["speaker_a_name"] = (data.get("speaker_a_name") or "Persona A").strip()
            style_a = ""

        if pb:
            out["voice_b"] = pb["voice"]
            out["speaker_b_name"] = pb["name"]
            style_b = personas_mod.style_instructions_for(pb["style"], pb.get("custom_style", ""))
        else:
            out["voice_b"] = (data.get("voice_b") or "").strip()
            out["speaker_b_name"] = (data.get("speaker_b_name") or "Persona B").strip()
            style_b = ""

        # Combinamos las personalidades de A y B en una sola instruccion para
        # que la IA escriba a cada quien con su estilo.
        blocks = []
        if style_a:
            blocks.append(f"La persona A ({out['speaker_a_name']}) habla asi: {style_a}")
        if style_b:
            blocks.append(f"La persona B ({out['speaker_b_name']}) habla asi: {style_b}")
        out["style_instructions"] = " ".join(blocks)
        return out

    # --- Narrador unico ---
    persona = personas_mod.get_persona(data.get("avatar_id") or "")
    if persona:
        out["persona_name"] = persona["name"]
        out["voice_override"] = persona["voice"]
        out["style_instructions"] = personas_mod.style_instructions_for(
            persona["style"], persona.get("custom_style", "")
        )
    else:
        # Sin avatar guardado: se puede elegir solo un estilo (preset).
        style_key = (data.get("style_key") or "").strip()
        if style_key:
            out["style_instructions"] = personas_mod.style_instructions_for(style_key, "")
    return out


def _merge_persona_into_options(options: dict, data: dict) -> None:
    """Resuelve avatar/podcast y lo guarda dentro de `options` (incluida la voz)."""
    persona = _resolve_persona_options(data)
    if persona["voice_override"]:
        options["voice"] = persona["voice_override"]
    options["style_instructions"] = persona["style_instructions"]
    options["persona_name"] = persona["persona_name"]
    options["podcast"] = persona["podcast"]
    options["voice_a"] = persona["voice_a"]
    options["voice_b"] = persona["voice_b"]
    options["speaker_a_name"] = persona["speaker_a_name"]
    options["speaker_b_name"] = persona["speaker_b_name"]


def _persona_kwargs(options: dict) -> dict:
    """Extrae de `options` los kwargs de personalidad/podcast para el pipeline."""
    return {
        "style_instructions": options.get("style_instructions", ""),
        "persona_name": options.get("persona_name", ""),
        "podcast": bool(options.get("podcast", False)),
        "voice_a": options.get("voice_a", ""),
        "voice_b": options.get("voice_b", ""),
        "speaker_a_name": options.get("speaker_a_name", ""),
        "speaker_b_name": options.get("speaker_b_name", ""),
    }


def _parse_urls(data: dict) -> list[str]:
    """
    Saca la lista de URLs del cuerpo de la peticion. Acepta:
      - "urls": ["...", "..."]  (lista)
      - "url" : "uno\\notro"     (texto con un enlace por renglon)
    Devuelve la lista limpia (sin renglones vacios).
    """
    raw = data.get("urls")
    if isinstance(raw, list):
        items = raw
    else:
        items = re.split(r"[\r\n]+", str(data.get("url") or ""))
    return [u.strip() for u in items if u and u.strip()]

# Estado de los trabajos (en memoria). clave = job_id
#   cada job: {status, phase, message, percent, error, prepared, options, review, result}
JOBS: dict[str, dict] = {}


# --------------------------------------------------------------------------
#  Pagina principal
# --------------------------------------------------------------------------
@app.route("/")
def index():
    missing = settings.missing_keys()
    voice_options = _voice_options()
    return render_template(
        "index.html",
        missing_keys=missing,
        avatar_enabled=settings.avatar_enabled,
        voice_options=voice_options,
        foreign_voices=foreign_accent_options(),
        persona_styles=personas_mod.style_options(),
        avatars=personas_mod.list_personas(),
        defaults={
            "voice": settings.tts_voice,
            "rate": settings.tts_rate,
            "duration": settings.video_duration,
            "style": settings.script_style,
            "cta": settings.call_to_action,
            "image_source": settings.image_source,
        },
    )


# --------------------------------------------------------------------------
#  Utilidad: armar la lista de escenas para la interfaz
# --------------------------------------------------------------------------
def _review_payload(job_id: str) -> dict:
    job = JOBS[job_id]
    prepared = job["prepared"]
    durations = planned_scene_durations(prepared)
    scenes = []
    for i, (scene, img) in enumerate(zip(prepared.scenes, prepared.images)):
        dur = round(durations[i], 1) if i < len(durations) else 0.0
        is_video = bool(getattr(img, "is_video", False))
        # Nombre a mostrar de quien habla (modo podcast) para el boton de play.
        speaker = (getattr(scene, "speaker", "") or "").upper()
        if prepared.podcast and speaker == "B":
            speaker_name = prepared.speaker_b_name or "Persona B"
        elif prepared.podcast:
            speaker_name = prepared.speaker_a_name or "Persona A"
        else:
            speaker_name = ""
        scenes.append({
            "index": i,
            "text": scene.text,
            "image_prompt": scene.image_prompt,
            "keyword": scene.keyword,
            "image_file": Path(img.path).name,
            "source": img.source,
            "is_video": is_video,
            "duration": dur,
            # Audio propio del video (Opcion A)
            "use_own_audio": bool(getattr(scene, "use_own_audio", False)),
            "own_audio_volume": round(float(getattr(scene, "own_audio_volume", 1.0)), 2),
            "own_audio_duration": round(float(getattr(scene, "own_audio_duration", 0.0)), 1),
            "can_own_audio": is_video,   # solo tiene sentido si la escena es video
            # Recorte del video (dejar solo un trozo)
            "trim_start": round(float(getattr(img, "trim_start", 0.0) or 0.0), 2),
            "trim_end": round(float(getattr(img, "trim_end", 0.0) or 0.0), 2),
            "media_duration": round(media_duration(img), 2) if is_video else 0.0,
            # Pedazos (mini-clips) de la escena, si tiene varios.
            "clips": [
                {
                    "file": c.get("file") or Path(c.get("path", "")).name,
                    "is_video": bool(c.get("is_video")),
                    "seconds": round(float(c.get("seconds", 0) or 0), 1),
                    "source": c.get("source", ""),
                }
                for c in (getattr(scene, "clips", None) or [])
            ],
            # Podcast: quien habla
            "speaker": speaker,
            "speaker_name": speaker_name,
        })
    return {
        "job_id": job_id,
        "title": prepared.title,
        "narration": prepared.narration,
        "titles": prepared.titles,
        "hashtags": prepared.hashtags,
        "duration": round(prepared.real_duration, 1),
        "warning": getattr(prepared, "warning", "") or "",
        "use_avatar": bool(job["options"].get("use_avatar", False)),
        "media_type": job["options"].get("media_type", "image"),
        "voice": prepared.voice,
        "podcast": bool(prepared.podcast),
        "persona_name": prepared.persona_name or "",
        "speaker_a_name": prepared.speaker_a_name or "",
        "speaker_b_name": prepared.speaker_b_name or "",
        "scenes": scenes,
    }


def _draft_payload(job_id: str) -> dict:
    """Lista de escenas del BORRADOR (texto + prompt, sin imagenes todavia)."""
    job = JOBS[job_id]
    prepared = job["prepared"]
    scenes = []
    for i, scene in enumerate(prepared.scenes):
        scenes.append({
            "index": i,
            "text": scene.text,
            "image_prompt": scene.image_prompt,
        })
    return {
        "job_id": job_id,
        "title": prepared.title,
        "titles": prepared.titles,
        "hashtags": prepared.hashtags,
        "warning": getattr(prepared, "warning", "") or "",
        "scenes": scenes,
    }


# --------------------------------------------------------------------------
#  PASO 1: preparar (guion + voz + imagenes)
# --------------------------------------------------------------------------
@app.route("/api/prepare", methods=["POST"])
def api_prepare():
    data = request.get_json(force=True) or {}
    urls = _parse_urls(data)
    if not urls:
        return jsonify({"error": "Pega la URL de una noticia primero."}), 400

    fresh = settings.reload()
    missing = fresh.missing_keys()
    if "GROQ_API_KEY" in missing:
        return jsonify({"error": "Faltan claves en tu archivo .env: " + ", ".join(missing)}), 400

    job_id = uuid.uuid4().hex[:12]
    options = {
        "duration": int(data.get("duration") or fresh.video_duration),
        "style": data.get("style") or fresh.script_style,
        "n_images": data.get("n_images") or "auto",
        "voice": data.get("voice") or fresh.tts_voice,
        "rate": data.get("rate") if data.get("rate") is not None else fresh.tts_rate,
        "cta": data.get("cta") or fresh.call_to_action,
        "image_source": data.get("image_source") or fresh.image_source,
        "media_type": (data.get("media_type") or "image").lower(),
        "subtitle_color": data.get("subtitle_color") or "amarillo",
        "subtitle_position": data.get("subtitle_position") or "center",
        "use_avatar": bool(data.get("use_avatar", fresh.avatar_enabled)),
        "music_mode": data.get("music_mode") or "auto",
        "music_volume": float(data.get("music_volume") or 0.15),
        "aspect": data.get("aspect") or "9:16",
    }
    _merge_persona_into_options(options, data)
    JOBS[job_id] = {
        "status": "running", "phase": "preparing", "message": "Iniciando...",
        "percent": 0, "error": None, "prepared": None, "options": options,
        "review": None, "result": None,
    }

    threading.Thread(target=_run_prepare, args=(job_id, urls, options), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_prepare(job_id: str, url, options: dict) -> None:
    def progress(msg: str, pct: int) -> None:
        JOBS[job_id]["message"] = msg
        JOBS[job_id]["percent"] = pct

    try:
        prepared = prepare_video(
            url,
            duration=options["duration"],
            style=options["style"],
            n_images=options.get("n_images", "auto"),
            voice=options["voice"],
            rate=options["rate"],
            cta=options["cta"],
            image_source=options["image_source"],
            media_type=options.get("media_type", "image"),
            progress=progress,
            **_persona_kwargs(options),
        )
        JOBS[job_id]["prepared"] = prepared
        JOBS[job_id]["phase"] = "review"
        JOBS[job_id]["status"] = "ready"
        JOBS[job_id]["percent"] = 100
        JOBS[job_id]["message"] = "Listo para revisar"
        JOBS[job_id]["review"] = _review_payload(job_id)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(exc)


# --------------------------------------------------------------------------
#  PASO 1 (YOUTUBE): preparar desde un link de video de YouTube
# --------------------------------------------------------------------------
@app.route("/api/prepare_youtube", methods=["POST"])
def api_prepare_youtube():
    data = request.get_json(force=True) or {}
    urls = _parse_urls(data)
    if not urls:
        return jsonify({"error": "Pega el enlace de un video de YouTube primero."}), 400

    fresh = settings.reload()
    missing = fresh.missing_keys()
    if "GROQ_API_KEY" in missing:
        return jsonify({"error": "Faltan claves en tu archivo .env: " + ", ".join(missing)}), 400

    job_id = uuid.uuid4().hex[:12]
    options = {
        "duration": int(data.get("duration") or fresh.video_duration),
        "style": data.get("style") or fresh.script_style,
        "n_images": data.get("n_images") or "auto",
        "voice": data.get("voice") or fresh.tts_voice,
        "rate": data.get("rate") if data.get("rate") is not None else fresh.tts_rate,
        "cta": data.get("cta") or fresh.call_to_action,
        "image_source": data.get("image_source") or fresh.image_source,
        "media_type": (data.get("media_type") or "image").lower(),
        "subtitle_color": data.get("subtitle_color") or "amarillo",
        "subtitle_position": data.get("subtitle_position") or "center",
        "use_avatar": bool(data.get("use_avatar", fresh.avatar_enabled)),
        "music_mode": data.get("music_mode") or "auto",
        "music_volume": float(data.get("music_volume") or 0.15),
        "aspect": data.get("aspect") or "9:16",
    }
    _merge_persona_into_options(options, data)
    JOBS[job_id] = {
        "status": "running", "phase": "preparing", "message": "Iniciando...",
        "percent": 0, "error": None, "prepared": None, "options": options,
        "review": None, "result": None,
    }

    threading.Thread(target=_run_prepare_youtube, args=(job_id, urls, options), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_prepare_youtube(job_id: str, url, options: dict) -> None:
    def progress(msg: str, pct: int) -> None:
        JOBS[job_id]["message"] = msg
        JOBS[job_id]["percent"] = pct

    try:
        prepared = prepare_youtube(
            url,
            duration=options["duration"],
            style=options["style"],
            n_images=options.get("n_images", "auto"),
            voice=options["voice"],
            rate=options["rate"],
            cta=options["cta"],
            image_source=options["image_source"],
            media_type=options.get("media_type", "image"),
            progress=progress,
            **_persona_kwargs(options),
        )
        JOBS[job_id]["prepared"] = prepared
        JOBS[job_id]["phase"] = "review"
        JOBS[job_id]["status"] = "ready"
        JOBS[job_id]["percent"] = 100
        JOBS[job_id]["message"] = "Listo para revisar"
        JOBS[job_id]["review"] = _review_payload(job_id)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(exc)


# --------------------------------------------------------------------------
#  MODO HISTORIA - PASO A: crear el borrador (guion + prompts, sin imagenes)
# --------------------------------------------------------------------------
@app.route("/api/draft_story", methods=["POST"])
def api_draft_story():
    data = request.get_json(force=True) or {}
    story = (data.get("story") or "").strip()
    if not story:
        return jsonify({"error": "Escribe tu historia primero."}), 400

    fresh = settings.reload()
    if "GROQ_API_KEY" in fresh.missing_keys():
        return jsonify({"error": "Falta la clave GROQ_API_KEY en tu archivo .env"}), 400

    job_id = uuid.uuid4().hex[:12]
    options = {
        "duration": int(data.get("duration") or fresh.video_duration),
        "n_images": data.get("n_images") or "auto",
        "style": fresh.script_style,
        "voice": data.get("voice") or fresh.tts_voice,
        "rate": data.get("rate") if data.get("rate") is not None else fresh.tts_rate,
        "cta": data.get("cta") or fresh.call_to_action,
        "image_source": data.get("image_source") or fresh.image_source,
        "media_type": (data.get("media_type") or "image").lower(),
        "subtitle_color": data.get("subtitle_color") or "amarillo",
        "subtitle_position": data.get("subtitle_position") or "center",
        "use_avatar": bool(data.get("use_avatar", fresh.avatar_enabled)),
        "music_mode": data.get("music_mode") or "auto",
        "music_volume": float(data.get("music_volume") or 0.15),
        "aspect": data.get("aspect") or "9:16",
    }
    _merge_persona_into_options(options, data)
    JOBS[job_id] = {
        "status": "running", "phase": "drafting", "message": "Iniciando...",
        "percent": 0, "error": None, "prepared": None, "options": options,
        "draft": None, "review": None, "result": None,
    }

    threading.Thread(target=_run_draft, args=(job_id, story, options), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_draft(job_id: str, story: str, options: dict) -> None:
    def progress(msg: str, pct: int) -> None:
        JOBS[job_id]["message"] = msg
        JOBS[job_id]["percent"] = pct

    try:
        prepared = draft_story(
            story,
            duration=options["duration"],
            n_images=options["n_images"],
            voice=options["voice"],
            rate=options["rate"],
            cta=options["cta"],
            image_source=options["image_source"],
            media_type=options.get("media_type", "image"),
            progress=progress,
            **_persona_kwargs(options),
        )
        JOBS[job_id]["prepared"] = prepared
        JOBS[job_id]["phase"] = "draft"
        JOBS[job_id]["status"] = "draft_ready"
        JOBS[job_id]["percent"] = 100
        JOBS[job_id]["message"] = "Borrador listo para revisar"
        JOBS[job_id]["draft"] = _draft_payload(job_id)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(exc)


# --------------------------------------------------------------------------
#  Editar el prompt de imagen de una escena (en el borrador)
# --------------------------------------------------------------------------
@app.route("/api/update_prompt", methods=["POST"])
def api_update_prompt():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        prompt = data.get("prompt") or ""
        update_scene_prompt(job["prepared"], index, prompt)
        # Si el usuario edito el dialogo en el borrador tambien, lo guardamos
        if data.get("text") is not None:
            update_scene_text(job["prepared"], index, data.get("text") or "")
        job["draft"] = _draft_payload(job_id)
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  MODO HISTORIA - PASO B: generar voz + imagenes desde el borrador aprobado
# --------------------------------------------------------------------------
@app.route("/api/generate_from_draft", methods=["POST"])
def api_generate_from_draft():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404

    job["phase"] = "preparing"
    job["status"] = "running"
    job["percent"] = 0
    job["message"] = "Generando voz e imagenes..."
    threading.Thread(target=_run_generate_from_draft, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_generate_from_draft(job_id: str) -> None:
    job = JOBS[job_id]

    def progress(msg: str, pct: int) -> None:
        job["message"] = msg
        job["percent"] = pct

    try:
        prepare_from_draft(job["prepared"], progress=progress)
        job["phase"] = "review"
        job["status"] = "ready"
        job["percent"] = 100
        job["message"] = "Listo para revisar"
        job["review"] = _review_payload(job_id)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        job["status"] = "error"
        job["error"] = str(exc)


# --------------------------------------------------------------------------
#  Subir musica de fondo (opcional) para el video
# --------------------------------------------------------------------------
@app.route("/api/upload_music", methods=["POST"])
def api_upload_music():
    job_id = request.form.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    if "music" not in request.files:
        return jsonify({"error": "No se recibio ningun archivo de musica."}), 400
    try:
        prepared = job["prepared"]
        file = request.files["music"]
        ext = Path(secure_filename(file.filename or "musica.mp3")).suffix.lower() or ".mp3"
        if ext not in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"):
            return jsonify({"error": "Formato no valido. Usa MP3, WAV, M4A, AAC, OGG o FLAC."}), 400
        dest = prepared.job_dir / f"musica{ext}"
        file.save(str(dest))
        prepared.music_path = dest
        return jsonify({"ok": True, "music_file": dest.name})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Quitar la musica de fondo
# --------------------------------------------------------------------------
@app.route("/api/remove_music", methods=["POST"])
def api_remove_music():
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    job["prepared"].music_path = None
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
#  Regenerar la imagen de una escena
# --------------------------------------------------------------------------
@app.route("/api/regenerate_image", methods=["POST"])
def api_regenerate_image():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404

    try:
        index = int(data.get("index"))
        mode = (data.get("mode") or "hybrid").lower()
        new_prompt = data.get("prompt")
        attempt = int(data.get("attempt") or 0)
        result = regenerate_scene_image(
            job["prepared"], index, mode=mode, new_prompt=new_prompt, attempt=attempt
        )
        job["review"] = _review_payload(job_id)
        return jsonify({
            "index": index,
            "image_file": Path(result.path).name,
            "source": result.source,
            "is_video": bool(getattr(result, "is_video", False)),
        })
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Subir una imagen propia para una escena
# --------------------------------------------------------------------------
@app.route("/api/upload_image", methods=["POST"])
def api_upload_image():
    job_id = request.form.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    if "image" not in request.files:
        return jsonify({"error": "No se recibio ninguna imagen."}), 400

    try:
        index = int(request.form.get("index"))
        prepared = job["prepared"]
        file = request.files["image"]
        ext = Path(secure_filename(file.filename or "img.jpg")).suffix.lower() or ".jpg"
        image_exts = (".jpg", ".jpeg", ".png", ".webp")
        video_exts = (".mp4", ".mov", ".webm", ".m4v")
        if ext not in image_exts + video_exts:
            return jsonify({"error": "Formato no valido. Usa JPG, PNG, WEBP (foto) o MP4, MOV, WEBM (video)."}), 400
        kind = "video" if ext in video_exts else "img"
        dest = prepared.job_dir / "images" / f"{kind}_{index:02d}_subida{ext}"
        file.save(str(dest))
        result = set_scene_image(prepared, index, dest, source="subida")
        job["review"] = _review_payload(job_id)
        return jsonify({
            "index": index,
            "image_file": dest.name,
            "source": "subida",
            "is_video": bool(getattr(result, "is_video", False)),
        })
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Editar el dialogo (texto narrado) de una escena
# --------------------------------------------------------------------------
@app.route("/api/update_scene", methods=["POST"])
def api_update_scene():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        text = data.get("text") or ""
        update_scene_text(job["prepared"], index, text)
        job["review"] = _review_payload(job_id)
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Eliminar una escena completa (imagen + dialogo)
# --------------------------------------------------------------------------
@app.route("/api/delete_scene", methods=["POST"])
def api_delete_scene():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        delete_scene(job["prepared"], index)
        job["review"] = _review_payload(job_id)
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Agregar una escena NUEVA (dialogo + imagen/video)
# --------------------------------------------------------------------------
@app.route("/api/add_scene", methods=["POST"])
def api_add_scene():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        text = data.get("text") or ""
        image_desc = data.get("image_desc") or data.get("prompt") or ""
        position = data.get("position")
        if position is not None:
            try:
                position = int(position)
            except (TypeError, ValueError):
                position = None
        add_scene(job["prepared"], text, image_desc=image_desc, position=position)
        job["review"] = _review_payload(job_id)
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  PASO 2: ensamblar el video final
# --------------------------------------------------------------------------
@app.route("/api/assemble", methods=["POST"])
def api_assemble():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404

    # Modo y volumen de musica (ajustables en la pantalla de revision)
    if data.get("music_mode"):
        job["options"]["music_mode"] = data.get("music_mode")
    if data.get("music_volume") is not None:
        try:
            job["options"]["music_volume"] = float(data.get("music_volume"))
        except (TypeError, ValueError):
            pass

    # Voz y avatar (ahora tambien se pueden cambiar en la pantalla de revision)
    # voice == "" significa "mantener la voz actual" (no regenerar).
    job["options"]["override_voice"] = (data.get("voice") or "").strip()
    if "use_avatar" in data:
        job["options"]["use_avatar"] = bool(data.get("use_avatar"))

    job["phase"] = "assembling"
    job["status"] = "running"
    job["percent"] = 0
    job["message"] = "Preparando ensamblaje..."
    threading.Thread(target=_run_assemble, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_assemble(job_id: str) -> None:
    job = JOBS[job_id]
    options = job["options"]

    def progress(msg: str, pct: int) -> None:
        job["message"] = msg
        job["percent"] = pct

    try:
        result = assemble_prepared(
            job["prepared"],
            subtitle_color=options["subtitle_color"],
            subtitle_position=options["subtitle_position"],
            use_avatar=options["use_avatar"],
            voice=options.get("override_voice") or None,
            music_mode=options.get("music_mode", "auto"),
            music_volume=float(options.get("music_volume", 0.15)),
            aspect=options.get("aspect", "9:16"),
            progress=progress,
        )
        job["status"] = "done"
        job["phase"] = "done"
        job["percent"] = 100
        job["message"] = "Listo!"
        job["result"] = {
            "video_file": result.video_path.name,
            "title": result.title,
            "narration": result.narration,
            "titles": result.titles,
            "hashtags": result.hashtags,
            "duration": round(result.duration, 1),
            "used_avatar": result.used_avatar,
        }
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        job["status"] = "error"
        job["error"] = str(exc)


# --------------------------------------------------------------------------
#  Estado de un trabajo
# --------------------------------------------------------------------------
@app.route("/api/status/<job_id>")
def api_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Trabajo no encontrado"}), 404
    return jsonify({
        "status": job["status"],
        "phase": job["phase"],
        "message": job["message"],
        "percent": job["percent"],
        "error": job["error"],
        "draft": job.get("draft"),
        "review": job["review"],
        "result": job["result"],
    })


# --------------------------------------------------------------------------
#  Servir imagenes de previsualizacion (durante la revision)
# --------------------------------------------------------------------------
@app.route("/preview/<job_id>/<path:filename>")
def serve_preview(job_id: str, filename: str):
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return "No encontrado", 404
    images_dir = job["prepared"].job_dir / "images"
    resp = send_from_directory(images_dir, filename)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------
#  Escuchar una MUESTRA de voz antes de elegirla
# --------------------------------------------------------------------------
# Carpeta donde guardamos las muestras de voz (se reutilizan = mas rapido).
_PREVIEW_DIR = settings.work_dir / "voice_previews"


@app.route("/api/preview_voice", methods=["POST"])
def api_preview_voice():
    """Genera (o reutiliza) un audio corto de ejemplo para la voz pedida y
    devuelve la URL para reproducirlo en el navegador."""
    data = request.get_json(force=True) or {}
    voice = _resolve_preview_voice(data.get("voice") or "")
    if not voice:
        return jsonify({"error": "No se indico ninguna voz."}), 400
    try:
        path = synthesize_voice_sample(voice, _PREVIEW_DIR)
        return jsonify({"ok": True, "voice": voice, "audio_url": f"/voice_preview/{path.name}"})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


@app.route("/voice_preview/<path:filename>")
def serve_voice_preview(filename: str):
    resp = send_from_directory(_PREVIEW_DIR, filename)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------
#  Escuchar el DIALOGO de UNA ESCENA (boton ▶️ de cada escena en la revision)
# --------------------------------------------------------------------------
@app.route("/api/preview_scene", methods=["POST"])
def api_preview_scene():
    """
    Genera (o reutiliza) el audio del dialogo de una escena, con la voz que le
    corresponde (la del avatar, o la voz A/B si es podcast), para que el usuario
    ESCUCHE como sonara esa escena antes de armar el video. Si el usuario editó
    el dialogo, se manda el texto nuevo y se regenera con ese texto.
    """
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    prepared = job["prepared"]
    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        return jsonify({"error": "Escena invalida."}), 400
    if index < 0 or index >= len(prepared.scenes):
        return jsonify({"error": "Escena fuera de rango."}), 400

    scene = prepared.scenes[index]
    # Texto: el que viene del front (por si edito y no ha guardado) o el guardado.
    text = (data.get("text") or scene.text or "").strip()
    if not text:
        return jsonify({"error": "Esta escena no tiene dialogo para escuchar."}), 400

    # Voz: si el front manda una voz concreta, se usa; si no, la voz efectiva de
    # la escena (avatar unico o la de quien habla en el podcast).
    override = (data.get("voice") or "").strip()
    voice = _resolve_preview_voice(override) if override else voice_for_scene(prepared, scene)
    voice = _resolve_preview_voice(voice)   # asegura una voz concreta

    try:
        path = synthesize_scene_preview(text, voice, _PREVIEW_DIR, rate=prepared.rate)
        return jsonify({
            "ok": True,
            "index": index,
            "voice": voice,
            "audio_url": f"/voice_preview/{path.name}",
        })
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Marcar/desmarcar una escena para USAR EL AUDIO PROPIO de su video (Opcion A)
# --------------------------------------------------------------------------
@app.route("/api/scene_audio", methods=["POST"])
def api_scene_audio():
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        use = bool(data.get("use_own_audio"))
        volume = data.get("volume")
        result = set_scene_own_audio(job["prepared"], index, use, volume)
        job["review"] = _review_payload(data.get("job_id"))
        return jsonify({**result, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Recortar el video de una escena (dejar solo un trozo: del segundo X al Y)
# --------------------------------------------------------------------------
@app.route("/api/scene_trim", methods=["POST"])
def api_scene_trim():
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        start = float(data.get("start") or 0.0)
        end = float(data.get("end") or 0.0)
        result = set_scene_trim(job["prepared"], index, start, end)
        job["review"] = _review_payload(data.get("job_id"))
        return jsonify({**result, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Varios PEDAZOS (mini-clips) dentro de una escena
# --------------------------------------------------------------------------
@app.route("/api/scene_clip_add", methods=["POST"])
def api_scene_clip_add():
    """Sube un pedazo (imagen o video corto) y lo agrega a una escena."""
    job_id = request.form.get("job_id")
    job = JOBS.get(job_id)
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    if "file" not in request.files:
        return jsonify({"error": "No se recibio ningun archivo."}), 400
    try:
        index = int(request.form.get("index"))
        seconds = float(request.form.get("seconds") or 2.0)
        prepared = job["prepared"]
        file = request.files["file"]
        ext = Path(secure_filename(file.filename or "clip.mp4")).suffix.lower() or ".mp4"
        image_exts = (".jpg", ".jpeg", ".png", ".webp")
        video_exts = (".mp4", ".mov", ".webm", ".m4v", ".gif")
        if ext not in image_exts + video_exts:
            return jsonify({"error": "Formato no valido. Usa JPG, PNG, WEBP, GIF o MP4, MOV, WEBM."}), 400
        is_video = ext in video_exts
        images_dir = prepared.job_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        n = len(getattr(prepared.scenes[index], "clips", []) or [])
        dest = images_dir / f"clip_{index:02d}_{n:02d}_{uuid.uuid4().hex[:6]}{ext}"
        file.save(str(dest))
        add_scene_clip(prepared, index, dest, is_video=is_video, seconds=seconds, source="subida")
        job["review"] = _review_payload(job_id)
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


@app.route("/api/scene_clip_remove", methods=["POST"])
def api_scene_clip_remove():
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        clip_index = int(data.get("clip_index"))
        remove_scene_clip(job["prepared"], index, clip_index)
        job["review"] = _review_payload(data.get("job_id"))
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


@app.route("/api/scene_clip_seconds", methods=["POST"])
def api_scene_clip_seconds():
    data = request.get_json(force=True) or {}
    job = JOBS.get(data.get("job_id"))
    if not job or not job.get("prepared"):
        return jsonify({"error": "Trabajo no encontrado o expirado."}), 404
    try:
        index = int(data.get("index"))
        clip_index = int(data.get("clip_index"))
        seconds = float(data.get("seconds") or 2.0)
        set_scene_clip_seconds(job["prepared"], index, clip_index, seconds)
        job["review"] = _review_payload(data.get("job_id"))
        return jsonify({"ok": True, "review": job["review"]})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  AVATARES personalizados (crear / listar / editar / borrar)
# --------------------------------------------------------------------------
@app.route("/api/avatars", methods=["GET", "POST"])
def api_avatars():
    if request.method == "GET":
        return jsonify({"avatars": personas_mod.list_personas()})
    data = request.get_json(force=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"error": "Ponle un nombre a tu avatar."}), 400
    if not (data.get("voice") or "").strip():
        return jsonify({"error": "Elige una voz para tu avatar."}), 400
    try:
        created = personas_mod.create_persona(data)
        return jsonify({"ok": True, "avatar": created})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


@app.route("/api/avatars/<persona_id>", methods=["PUT", "DELETE"])
def api_avatar_detail(persona_id: str):
    if request.method == "DELETE":
        ok = personas_mod.delete_persona(persona_id)
        if not ok:
            return jsonify({"error": "No encontre ese avatar."}), 404
        return jsonify({"ok": True})
    data = request.get_json(force=True) or {}
    try:
        updated = personas_mod.update_persona(persona_id, data)
        return jsonify({"ok": True, "avatar": updated})
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


# --------------------------------------------------------------------------
#  Servir y descargar los videos finales
# --------------------------------------------------------------------------
@app.route("/video/<path:filename>")
def serve_video(filename: str):
    return send_from_directory(settings.output_dir, filename)
@app.route("/download/<path:filename>")
def download_video(filename: str):
    return send_from_directory(settings.output_dir, filename, as_attachment=True)


def _open_browser():
    try:
        import webbrowser
        webbrowser.open("http://localhost:5000")
    except Exception:
        pass


if __name__ == "__main__":
    print("=" * 60)
    print("  ViroFeed AI Personal")
    print("  VERSION DEL CODIGO: 23 (subtitulos podcast + recortar video + pedazos por escena)")
    print("  Abriendo en tu navegador: http://localhost:5000")
    print("  (Para cerrar el programa, cierra esta ventana)")
    print("=" * 60)
    threading.Timer(1.5, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
