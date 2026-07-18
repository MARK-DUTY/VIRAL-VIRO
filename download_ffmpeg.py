#!/usr/bin/env python3
"""
Descargador automatico de FFmpeg para ProCam (Windows)

FFmpeg es el motor gratuito que graba la pantalla. Este script lo descarga
solo (una sola vez) y deja el ffmpeg.exe dentro de la carpeta 'ffmpeg/'
al lado de este archivo. ProCam lo busca ahi automaticamente.

Uso:  python download_ffmpeg.py
"""

import os
import sys
import shutil
import tempfile
import zipfile
import urllib.request

# Build oficial de FFmpeg para Windows (BtbN, gratis)
FFMPEG_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


def ffmpeg_target_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "ffmpeg", "ffmpeg.exe")


def is_installed() -> bool:
    return os.path.exists(ffmpeg_target_path())


def _progress(block_num, block_size, total_size):
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    pct = min(100, downloaded * 100 // total_size)
    mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    sys.stdout.write(f"\r   Descargando... {pct}%  ({mb:.1f}/{total_mb:.1f} MB)")
    sys.stdout.flush()


def download() -> bool:
    dest = ffmpeg_target_path()
    if os.path.exists(dest):
        print("FFmpeg ya estaba instalado. Nada que hacer.")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp_zip = os.path.join(tempfile.gettempdir(), "ffmpeg_download.zip")

    try:
        print("Descargando FFmpeg (unos 80-120 MB, puede tardar varios minutos)...")
        urllib.request.urlretrieve(FFMPEG_URL, tmp_zip, _progress)
        print("\n   Extrayendo ffmpeg.exe...")

        extracted = False
        with zipfile.ZipFile(tmp_zip) as z:
            for name in z.namelist():
                # Buscamos .../bin/ffmpeg.exe dentro del zip
                if name.replace("\\", "/").endswith("bin/ffmpeg.exe"):
                    with z.open(name) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
                    extracted = True
                    break

        try:
            os.remove(tmp_zip)
        except OSError:
            pass

        if extracted and os.path.exists(dest):
            print("FFmpeg instalado correctamente en:")
            print(f"   {dest}")
            return True
        print("ERROR: no se encontro ffmpeg.exe dentro del archivo descargado.")
        return False

    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR al descargar FFmpeg: {exc}")
        print("Revisa tu conexion a internet e intenta de nuevo.")
        return False


if __name__ == "__main__":
    ok = download()
    sys.exit(0 if ok else 1)
