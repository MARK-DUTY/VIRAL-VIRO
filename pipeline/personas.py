"""
AVATARES / PERSONAJES personalizados de ViroFeed.

Un "avatar" aqui NO es un video de una cara: es una PERSONALIDAD guardada que
combina:
  - un NOMBRE que el usuario le pone (ej. "Mr. Doriga", "Dona Pelos", "El Galan")
  - una VOZ (que ademas define el ACENTO/pais: es-MX, es-CO, es-CL, es-ES, es-PR...)
  - un ESTILO de hablar (serio de noticiero, comico, chismoso, galan, etc.)

El estilo NO clona la voz real de nadie: le dice a la IA COMO ESCRIBIR el guion
(vocabulario, tono, actitud). El acento lo pone la voz elegida.

Los avatares se guardan en un archivo JSON dentro de la carpeta de trabajo
(work/avatars.json), asi el usuario los reutiliza cada dia sin volver a crearlos.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from .config import settings

# --------------------------------------------------------------------------
#  ESTILOS de personalidad (como habla el avatar). Cada uno le da a la IA
#  instrucciones de TONO y VOCABULARIO para escribir el guion.
# --------------------------------------------------------------------------
STYLE_PRESETS: dict[str, dict] = {
    "neutral": {
        "label": "Normal / neutral",
        "instructions": "",
    },
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


def style_options() -> list[dict]:
    """Lista de estilos para el menu de la interfaz."""
    return [{"value": k, "label": v["label"]} for k, v in STYLE_PRESETS.items()]


def style_instructions_for(style: str, custom_style: str = "") -> str:
    """
    Devuelve las instrucciones de TONO para inyectar en el prompt de la IA.
      - Si style == 'custom', usa el texto libre que escribio el usuario.
      - Si es un preset conocido, usa sus instrucciones.
      - Si no, cadena vacia (estilo normal).
    """
    if (style or "").strip().lower() == "custom":
        return (custom_style or "").strip()
    preset = STYLE_PRESETS.get((style or "").strip().lower())
    return preset["instructions"] if preset else ""


# --------------------------------------------------------------------------
#  ACENTOS / PAISES (cada pais tiene voces nativas en Edge TTS)
# --------------------------------------------------------------------------
# Codigo de locale -> nombre amigable del pais/acento.
ACCENT_COUNTRIES: dict[str, str] = {
    "es-MX": "Mexico", "es-ES": "Espana", "es-AR": "Argentina",
    "es-CO": "Colombia", "es-US": "Estados Unidos", "es-CL": "Chile",
    "es-PE": "Peru", "es-VE": "Venezuela", "es-EC": "Ecuador",
    "es-GT": "Guatemala", "es-CR": "Costa Rica", "es-PA": "Panama",
    "es-DO": "Rep. Dominicana", "es-UY": "Uruguay", "es-PY": "Paraguay",
    "es-BO": "Bolivia", "es-SV": "El Salvador", "es-HN": "Honduras",
    "es-NI": "Nicaragua", "es-PR": "Puerto Rico", "es-CU": "Cuba",
    "es-GQ": "Guinea Ecuatorial",
}


def country_for_voice(voice: str) -> str:
    """Nombre del pais/acento a partir del nombre de la voz (ej. es-CO -> Colombia)."""
    locale = "-".join((voice or "").split("-")[:2])
    return ACCENT_COUNTRIES.get(locale, locale or "Espanol")


# --------------------------------------------------------------------------
#  PERSISTENCIA de los avatares (JSON en la carpeta de trabajo)
# --------------------------------------------------------------------------
_LOCK = threading.Lock()


def _store_path() -> Path:
    return settings.work_dir / "avatars.json"


def _load_all() -> list[dict]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:  # noqa: BLE001
        pass
    return []


def _save_all(items: list[dict]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean(persona: dict) -> dict:
    """Normaliza/valida los campos de un avatar."""
    name = (persona.get("name") or "").strip() or "Avatar sin nombre"
    voice = (persona.get("voice") or "").strip() or settings.tts_voice
    style = (persona.get("style") or DEFAULT_STYLE).strip()
    custom_style = (persona.get("custom_style") or "").strip()
    gender = (persona.get("gender") or "").strip().lower()
    if gender not in ("hombre", "mujer"):
        gender = "mujer" if _looks_female(voice) else "hombre"
    return {
        "id": persona.get("id") or uuid.uuid4().hex[:12],
        "name": name,
        "voice": voice,
        "style": style,
        "custom_style": custom_style,
        "gender": gender,
        "accent": country_for_voice(voice),
    }


# Nombres comunes de voces femeninas en espanol de Edge TTS (para adivinar genero).
_FEMALE_VOICE_NAMES = {
    "dalia", "elvira", "salome", "paloma", "larissa", "ximena", "sabina",
    "tania", "marisol", "yolanda", "nuria", "renata", "emilia", "julia",
    "camila", "valentina", "abril", "luciana", "catalina", "amanda",
    "estrella", "vera", "marta", "irene", "xiaoxiao", "sunhi", "nanami",
    "jenny", "denise", "elsa", "katja", "francisca",
}


def _looks_female(voice: str) -> bool:
    name = (voice or "").lower()
    return any(fn in name for fn in _FEMALE_VOICE_NAMES)


def list_personas() -> list[dict]:
    """Devuelve todos los avatares guardados (normalizados)."""
    with _LOCK:
        return [_clean(p) for p in _load_all()]


def get_persona(persona_id: str) -> dict | None:
    """Busca un avatar por su id. None si no existe."""
    if not persona_id:
        return None
    for p in list_personas():
        if p["id"] == persona_id:
            return p
    return None


def create_persona(persona: dict) -> dict:
    """Crea y guarda un avatar nuevo. Devuelve el avatar creado."""
    with _LOCK:
        items = _load_all()
        new = _clean({**persona, "id": None})
        items.append(new)
        _save_all(items)
        return new


def update_persona(persona_id: str, persona: dict) -> dict:
    """Actualiza un avatar existente. Lanza error si no existe."""
    with _LOCK:
        items = _load_all()
        for i, p in enumerate(items):
            if (p.get("id") or "") == persona_id:
                merged = _clean({**p, **persona, "id": persona_id})
                items[i] = merged
                _save_all(items)
                return merged
    raise ValueError("No encontre ese avatar para actualizar.")


def delete_persona(persona_id: str) -> bool:
    """Borra un avatar por id. Devuelve True si se borro."""
    with _LOCK:
        items = _load_all()
        remaining = [p for p in items if (p.get("id") or "") != persona_id]
        if len(remaining) == len(items):
            return False
        _save_all(remaining)
        return True
