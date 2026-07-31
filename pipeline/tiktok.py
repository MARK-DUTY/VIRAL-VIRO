"""
Lector de TikTok (modo TikTok del programa).

Saca el TEXTO de un video de TikTok (subtitulos + descripcion + hashtags) y lo
entrega como un `Article`, EXACTAMENTE igual que `youtube.py` hace con un video
de YouTube y `article.py` con una noticia. Asi el resto del programa (guion,
voz, imagenes, video) funciona sin ningun cambio: solo cambiamos de donde sale
el texto.

IMPORTANTE: este lector usa SOLO `requests` (que ya viene instalado). No hace
falta instalar ninguna libreria nueva, asi el modo TikTok funciona sin que
tengas que ejecutar comandos tecnicos.

COMO FUNCIONA (en simple):
- Cada pagina de un video de TikTok trae, escondido en el HTML, un bloque de
  datos en formato JSON llamado `__UNIVERSAL_DATA_FOR_REHYDRATION__`. Ahi esta
  la descripcion del video, sus hashtags, el autor y, cuando el video los tiene,
  los SUBTITULOS automaticos (lo que se dice hablado).
- Preferimos los subtitulos (el texto hablado). Si el video no tiene, usamos su
  descripcion + hashtags como respaldo.
"""
from __future__ import annotations

import html as _html
import json
import random
import re
import time

import requests

from .article import Article

# Varios "User-Agent" (navegadores) para rotar y parecer mas humano. Asi es
# menos probable que TikTok nos confunda con un robot y nos bloquee.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# Cabecera base para que TikTok nos responda como si fueramos un navegador normal.
# Cuanto mas "de navegador real" se vea, mas probable es que nos entregue la
# pagina COMPLETA (con los datos del video) en vez de una version recortada.
_HEADERS = {
    "User-Agent": _USER_AGENTS[0],
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.tiktok.com/",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    # Cookie que le dice a TikTok que ya elegimos region/consentimiento. Reduce
    # el riesgo de que nos mande a una pantalla intermedia.
    "Cookie": "tt_csrf_token=1; tt_chain_token=1",
}


class TikTokBlockedError(ValueError):
    """TikTok bloqueo temporalmente la peticion (429 / captcha / login wall)."""


def _looks_blocked(resp: requests.Response) -> bool:
    """Detecta si TikTok nos mando a captcha, login o nos limito (429)."""
    final_url = (resp.url or "").lower()
    if resp.status_code in (403, 429):
        return True
    if "/login" in final_url or "captcha" in final_url or "/notfound" in final_url:
        return True
    # A veces responde 200 con una pagina de verificacion muy corta.
    body = (resp.text or "")
    if resp.status_code == 200 and len(body) < 2000 and (
        "captcha" in body.lower() or "verify to continue" in body.lower()
    ):
        return True
    return False


def _http_get(url: str, timeout: int = 25, max_retries: int = 3) -> requests.Response:
    """
    Descarga una URL con reintentos y deteccion del bloqueo de TikTok.

    Si TikTok nos bloquea (429 / 403 / captcha), espera un poco y reintenta con
    otro navegador. Si tras los reintentos sigue bloqueado, lanza un mensaje
    claro en espanol para el usuario.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        headers = dict(_HEADERS)
        # Rotamos el navegador en cada intento
        headers["User-Agent"] = _USER_AGENTS[attempt % len(_USER_AGENTS)]
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1) + random.uniform(0, 1))
            continue

        if _looks_blocked(resp):
            last_error = TikTokBlockedError("bloqueo temporal de TikTok")
            # Espera creciente (2s, 4s, 6s...) antes de reintentar
            if attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1) + random.uniform(0, 1))
            continue

        if resp.status_code >= 400:
            last_error = ValueError(f"{resp.status_code} al abrir TikTok")
            time.sleep(1.0 + random.uniform(0, 0.5))
            continue

        return resp  # todo bien

    # Si llegamos aqui, no se pudo. Mensaje claro segun el motivo.
    if isinstance(last_error, TikTokBlockedError):
        raise TikTokBlockedError(
            "TikTok bloqueo la peticion por ahora (te pidio verificar que no "
            "eres un robot o inicio de sesion). Esto pasa cuando se hacen varias "
            "peticiones seguidas. Soluciones: 1) espera de 15 a 30 minutos y "
            "vuelve a intentar, 2) usa el modo 'Noticia (URL)' o 'YouTube' "
            "mientras tanto, o 3) prueba con otro video."
        )
    raise ValueError(
        f"No pude abrir el video de TikTok. Revisa el enlace o tu internet. "
        f"Detalle: {last_error}"
    )


def _clean(text: str) -> str:
    """Limpia el texto: quita etiquetas de subtitulos, saltos de linea y espacios dobles."""
    text = _html.unescape(text or "")
    text = re.sub(r"\[[^\]]{0,40}\]", " ", text)   # quitar [Music], etc.
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_tiktok_url(url: str) -> bool:
    """True si el enlace parece de TikTok (incluye los cortos vm./vt.)."""
    return bool(re.search(r"(?:^|\.)tiktok\.com/", (url or "").strip(), re.IGNORECASE))


def _normalize_url(url: str, timeout: int = 25) -> str:
    """
    Devuelve la URL final del video.

    Los enlaces cortos que da la app (vm.tiktok.com/XXXX o vt.tiktok.com/XXXX)
    redirigen al enlace largo real; los seguimos para quedarnos con el definitivo.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("No diste ningun enlace de TikTok.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if not _is_tiktok_url(url):
        raise ValueError(
            "No reconoci el enlace de TikTok. Pega el enlace del video, por "
            "ejemplo: https://www.tiktok.com/@usuario/video/1234567890123456789 "
            "(tambien sirve el enlace corto vm.tiktok.com/XXXX que copia la app)."
        )
    # Enlaces cortos: seguir la redireccion para obtener la URL larga real.
    if re.search(r"(?:vm|vt|m)\.tiktok\.com/", url, re.IGNORECASE):
        try:
            resp = _http_get(url, timeout=timeout)
            if resp.url:
                return resp.url.split("?")[0]
        except TikTokBlockedError:
            raise
        except Exception:
            # Si falla la resolucion, devolvemos el original y probamos igual.
            return url
    return url


def _find_json_object(text: str, marker: str) -> dict | None:
    """
    Busca `marker` dentro del HTML y extrae el objeto JSON {...} que viene
    justo despues, contando llaves para tomar el objeto completo (sin libreria).
    """
    idx = text.find(marker)
    if idx == -1:
        return None
    start = text.find("{", idx)
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    blob = text[start : i + 1]
                    try:
                        return json.loads(blob)
                    except json.JSONDecodeError:
                        return None
    return None


def _get_item_struct(page: str) -> dict | None:
    """
    Saca el objeto del video (itemStruct) del bloque de datos de TikTok.

    Intenta primero el bloque nuevo (__UNIVERSAL_DATA_FOR_REHYDRATION__) y, si no
    esta, el antiguo (SIGI_STATE). Ambos guardan lo mismo en distinto lugar.
    """
    # Formato NUEVO: __UNIVERSAL_DATA_FOR_REHYDRATION__
    data = _find_json_object(page, "__UNIVERSAL_DATA_FOR_REHYDRATION__")
    if data:
        scope = data.get("__DEFAULT_SCOPE__") or {}
        detail = scope.get("webapp.video-detail") or {}
        item_info = detail.get("itemInfo") or {}
        item = item_info.get("itemStruct")
        if isinstance(item, dict):
            return item

    # Formato ANTIGUO: SIGI_STATE  ->  ItemModule -> { "<id>": {...} }
    sigi = _find_json_object(page, '"SIGI_STATE"')
    if not sigi:
        sigi = _find_json_object(page, "window['SIGI_STATE']")
    if sigi:
        item_module = sigi.get("ItemModule") or {}
        if isinstance(item_module, dict) and item_module:
            # Tomamos el primer video del modulo
            first = next(iter(item_module.values()), None)
            if isinstance(first, dict):
                return first
    return None


def _pick_subtitle(item: dict) -> dict | None:
    """Elige la mejor pista de subtitulos: preferimos espanol, luego ingles."""
    video = item.get("video") or {}
    infos = video.get("subtitleInfos") or []
    if not isinstance(infos, list) or not infos:
        return None

    def score(t: dict) -> tuple:
        lang = (t.get("LanguageCodeName") or t.get("Language") or "").lower()
        is_spanish = lang.startswith("es")
        is_english = lang.startswith("en")
        fmt = (t.get("Format") or "").lower()
        is_vtt = "vtt" in fmt or "webvtt" in fmt
        return (is_spanish, is_english, is_vtt)

    return sorted(infos, key=score, reverse=True)[0]


def _parse_vtt(text: str) -> str:
    """Convierte un archivo de subtitulos WEBVTT en texto plano corrido."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if line.isdigit():                       # numero de bloque
            continue
        if "-->" in line:                         # linea de tiempos
            continue
        line = re.sub(r"<[^>]+>", "", line)       # etiquetas <c>, <00:00:01.000>
        if line:
            lines.append(line)
    # Quitar repeticiones seguidas (los subtitulos suelen repetir la frase)
    out: list[str] = []
    for ln in lines:
        if not out or out[-1] != ln:
            out.append(ln)
    return _clean(" ".join(out))


def _fetch_subtitle_text(track: dict, timeout: int = 25) -> str:
    """Descarga y arma el texto de la pista de subtitulos elegida."""
    if not track:
        return ""
    url = track.get("Url") or track.get("url")
    if not url:
        return ""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return _parse_vtt(resp.text)
    except Exception:
        return ""


def _hashtags_text(item: dict) -> str:
    """Junta los hashtags del video en una linea (ayuda al contexto del guion)."""
    tags: list[str] = []
    for extra in item.get("textExtra") or []:
        name = (extra.get("hashtagName") or "").strip()
        if name:
            tags.append("#" + name)
    return " ".join(tags)


def _stickers_text(item: dict) -> str:
    """
    Saca el TEXTO PEGADO en pantalla (las "calcomanias"/stickers que el creador
    escribe encima del video, ej: 'MINIALERTA DE OFERTA', '-57% Descuento').
    Es texto muy util porque suele ser el mensaje principal del video.
    """
    pieces: list[str] = []
    for st in item.get("stickersOnItem") or []:
        for t in st.get("stickerText") or []:
            t = (t or "").replace("\n", " ").strip()
            if t:
                pieces.append(t)
    return " ".join(pieces)


def _join_unique(parts: list[str]) -> str:
    """Une varios textos en uno, saltando los que se repiten identicos."""
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        p = (p or "").strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return " ".join(out)


def _oembed(url: str, timeout: int = 20) -> tuple[str, str]:
    """
    RESPALDO robusto: la API publica oEmbed de TikTok.

    Funciona SIN inicio de sesion y desde cualquier pais, aunque TikTok le
    entregue a la PC del usuario una pagina recortada (sin los datos del video).
    Devuelve (descripcion/titulo, nombre del autor). Si falla, ("", "").
    """
    try:
        resp = requests.get(
            "https://www.tiktok.com/oembed",
            params={"url": url},
            headers={"User-Agent": _USER_AGENTS[0], "Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("title") or "").strip(), (data.get("author_name") or "").strip()
    except Exception:
        return "", ""


def extract_tiktok(url: str, timeout: int = 25) -> Article:
    """
    Lee un video de TikTok y devuelve un Article (url + titulo + texto).

    El texto sale de los SUBTITULOS del video. Si el video no tiene subtitulos,
    usamos su DESCRIPCION + HASHTAGS como respaldo. Lanza ValueError con un
    mensaje claro si no hay suficiente texto para crear un guion.
    """
    final_url = _normalize_url(url, timeout=timeout)

    # 1) Bajamos la pagina del video. Si TikTok bloquea, seguimos con oEmbed.
    page = ""
    try:
        page = _http_get(final_url, timeout=timeout).text
    except TikTokBlockedError:
        page = ""

    item = _get_item_struct(page) if page else None

    title = ""
    nickname = ""
    parts: list[str] = []

    if item:
        author = item.get("author") or {}
        nickname = (author.get("nickname") or author.get("uniqueId") or "").strip()
        description = (item.get("desc") or "").strip()
        hashtags = _hashtags_text(item)
        stickers = _stickers_text(item)          # texto PEGADO en pantalla
        title = description[:80].strip() or (f"Video de {nickname}" if nickname else "")

        # Subtitulos automaticos (texto hablado). OJO: su enlace es un CDN firmado
        # que a veces se bloquea segun el pais; por eso NO dependemos solo de esto.
        transcript = ""
        track = _pick_subtitle(item)
        if track:
            transcript = _fetch_subtitle_text(track, timeout=timeout)

        # Juntamos TODO el texto disponible (sin repetir): lo hablado + lo pegado
        # en pantalla + la descripcion + los hashtags. Asi hay material de sobra.
        parts = [transcript, stickers, description, hashtags]

    text = _clean(_join_unique(parts))

    # 2) RESPALDO oEmbed: si con la pagina no juntamos suficiente texto (por
    #    bloqueo o pagina recortada segun la region), pedimos la descripcion por
    #    la API publica de TikTok, que funciona desde cualquier pais.
    if len(text) < 120:
        o_desc, o_author = _oembed(final_url, timeout=timeout)
        if o_author and not nickname:
            nickname = o_author
        if o_desc:
            if not title:
                title = o_desc[:80].strip()
            if o_desc.lower() not in text.lower():
                text = _clean((text + " " + o_desc).strip())

    # Respaldo del titulo: la etiqueta <title> de la pagina
    if not title and page:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).replace(" | TikTok", "").strip()
    title = _clean(title) or (f"Video de {nickname}" if nickname else "Video de TikTok")

    article = Article(url=url, title=title, text=text)
    if not article.is_usable:
        raise ValueError(
            "Pude abrir el TikTok, pero no encontre suficiente texto para armar un "
            "guion (ni subtitulos, ni texto en pantalla, ni una descripcion larga). "
            "Los videos muy cortos a veces traen poco texto escrito. Prueba con un "
            "video que tenga subtitulos, texto en pantalla o una descripcion mas "
            "larga; tambien puedes pegar 2 o 3 TikToks del mismo tema para juntar "
            "mas material."
        )
    return article


def extract_tiktoks(urls: list[str], timeout: int = 25) -> Article:
    """
    Lee VARIOS videos de TikTok (del mismo tema) y combina su texto en un solo
    Article. Asi hay material de sobra para videos largos.

    - Lee cada video; si alguno falla, lo salta (no rompe todo el proceso).
    - El titulo es el del primer video que se pudo leer.
    - El texto es la union de todos.

    Lanza ValueError solo si NINGUNO de los videos se pudo leer.
    """
    urls = [u.strip() for u in (urls or []) if u and u.strip()]
    if not urls:
        raise ValueError("No diste ningun enlace de TikTok.")
    if len(urls) == 1:
        return extract_tiktok(urls[0], timeout=timeout)

    title = ""
    parts: list[str] = []
    errors: list[str] = []
    blocked = False
    for u in urls:
        try:
            art = extract_tiktok(u, timeout=timeout)
            if not title:
                title = art.title
            parts.append(art.text)
        except TikTokBlockedError as exc:
            blocked = True
            errors.append(f"- {u}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"- {u}: {exc}")

    if not parts:
        if blocked:
            raise TikTokBlockedError(
                "TikTok bloqueo las peticiones por ahora (te pidio verificar que "
                "no eres un robot). Espera de 15 a 30 minutos y reintenta, usa el "
                "modo 'Noticia (URL)' o 'YouTube' mientras tanto, o prueba con "
                "otros videos."
            )
        raise ValueError(
            "No pude leer NINGUNO de los TikToks que pegaste. Revisa que tengan "
            "subtitulos o una descripcion con texto. Detalle:\n" + "\n".join(errors)
        )

    combined = "\n\n".join(parts)
    article = Article(url=urls[0], title=title or "Video de TikTok", text=_clean(combined))
    print(f"[tiktok] {len(parts)} de {len(urls)} videos combinados")
    return article
