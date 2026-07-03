#!/usr/bin/env python3
"""
ProCam - Captura de pantalla y GRABADOR de video desde la BARRA DE TAREAS (Windows)

COMO FUNCIONA:
- El programa se pone como un iconito junto al reloj de Windows
  (abajo a la derecha, en la bandeja del sistema).

  SCREENSHOT (foto):
  - CLIC en el icono  ->  seleccionas el area con el mouse  ->  se copia solo.

  VIDEO (grabar pantalla):
  - CLIC DERECHO en el icono  ->  "Grabar video".
  - Seleccionas el area a grabar con el mouse.
  - Aparece un panel con: Comenzar / Pausar / Detener.
      · Comenzar: clic en el boton  o  tecla ENTER
      · Pausar/Reanudar: clic en el boton  o  BARRA ESPACIADORA
      · Detener: clic en el boton  o  clic en el icono ROJO de la barra
  - Al detener: ves el video y eliges Guardar / Descartar / Copiar
    (Copiar = lo pega y lo mandas sin guardar nada).

TODO CON EL MOUSE (y atajos de teclado opcionales).

Necesita: pip install pystray Pillow   +   FFmpeg (se descarga solo).
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab, ImageTk, Image, ImageDraw

try:
    import pystray
except ImportError:
    print("Falta la libreria 'pystray'. Instalala con:  pip install pystray")
    sys.exit(1)

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ======================================================================
#  Soporte de VARIAS PANTALLAS (monitores)
# ======================================================================
def _enable_dpi_awareness():
    """Hace que las coordenadas coincidan con los pixeles reales (importante
    con varias pantallas y escalado de Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


def virtual_screen_bounds():
    """Devuelve (x, y, ancho, alto) del ESCRITORIO COMPLETO que abarca TODAS
    las pantallas. Asi el selector cubre los dos monitores."""
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            x = u.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            y = u.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            w = u.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            h = u.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            if w > 0 and h > 0:
                return x, y, w, h
        except Exception:  # noqa: BLE001
            pass
    # Fallback: solo la pantalla principal
    tmp = tk.Tk()
    tmp.withdraw()
    w, h = tmp.winfo_screenwidth(), tmp.winfo_screenheight()
    tmp.destroy()
    return 0, 0, w, h


# ======================================================================
#  Iconos de la bandeja (camarita normal y camarita ROJA al grabar)
# ======================================================================
def make_tray_icon(recording: bool = False) -> Image.Image:
    body = "#e53935" if recording else "#3949ab"
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 20, 56, 52], radius=6, fill=body)
    d.rectangle([24, 14, 40, 22], fill=body)
    d.ellipse([24, 28, 40, 44], fill="white")
    d.ellipse([28, 32, 36, 40], fill=body)
    if recording:
        # punto rojo de "REC"
        d.ellipse([44, 8, 58, 22], fill="#ff1744")
    else:
        d.ellipse([46, 24, 52, 30], fill="white")
    return img


# ======================================================================
#  FFmpeg: buscarlo (carpeta local ffmpeg/ o en el PATH)
# ======================================================================
def find_ffmpeg() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(here, "ffmpeg", "ffmpeg.exe")
    if os.path.exists(local):
        return local
    found = shutil.which("ffmpeg")
    return found


# ======================================================================
#  Copiar al portapapeles
# ======================================================================
def copy_image_to_clipboard(image) -> bool:
    if sys.platform != "win32":
        return False
    try:
        temp_path = os.path.join(os.getenv("TEMP", os.getcwd()), "procam_clip.png")
        image.save(temp_path, "PNG")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            f"$img=[System.Drawing.Image]::FromFile('{temp_path}'); "
            "[System.Windows.Forms.Clipboard]::SetImage($img); "
            "$img.Dispose()"
        )
        # -STA: el portapapeles requiere este modo de hilo en Windows
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       check=True, creationflags=NO_WINDOW)
        return True
    except Exception:  # noqa: BLE001
        return False


def copy_file_to_clipboard(path: str) -> bool:
    """Copia un ARCHIVO (video) al portapapeles como 'archivo', para poder
    pegarlo en un chat / correo / carpeta y enviarlo sin guardarlo aparte."""
    if sys.platform != "win32":
        return False
    try:
        safe = path.replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$c = New-Object System.Collections.Specialized.StringCollection; "
            f"$c.Add('{safe}'); "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($c)"
        )
        # -STA es OBLIGATORIO para copiar archivos al portapapeles
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       check=True, creationflags=NO_WINDOW)
        return True
    except Exception:  # noqa: BLE001
        return False


# ======================================================================
#  Selector de region (reutilizable para foto y video)
# ======================================================================
class RegionSelector:
    """Overlay a pantalla completa. Llama on_selected(x1,y1,x2,y2) al soltar,
    o on_cancel() si se cancela (clic derecho / Escape / area muy chica)."""

    def __init__(self, parent, hint, on_selected, on_cancel):
        self.parent = parent
        self.on_selected = on_selected
        self.on_cancel = on_cancel
        self.start_x = self.start_y = 0
        self.cur_x = self.cur_y = 0
        self.selecting = False
        self.rect_id = None

        # Cubrir TODAS las pantallas (escritorio virtual completo)
        self.vx, self.vy, vw, vh = virtual_screen_bounds()

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)               # sin barra: permite abarcar 2 monitores
        self.win.geometry(f"{vw}x{vh}+{self.vx}+{self.vy}")
        self.win.attributes("-alpha", 0.25)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black", cursor="crosshair")

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Texto de ayuda centrado en cada mitad (por si hay 2 pantallas)
        self.canvas.create_text(
            vw // 2, 40, text=hint, fill="white", font=("Arial", 15, "bold")
        )

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", lambda e: self._cancel())
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.focus_force()

    def _press(self, event):
        self.selecting = True
        self.start_x, self.start_y = event.x_root, event.y_root
        self.cur_x, self.cur_y = self.start_x, self.start_y

    def _drag(self, event):
        if not self.selecting:
            return
        self.cur_x, self.cur_y = event.x_root, event.y_root
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        # Coordenadas del canvas = globales menos el origen del escritorio virtual
        x1, y1 = min(self.start_x, self.cur_x), min(self.start_y, self.cur_y)
        x2, y2 = max(self.start_x, self.cur_x), max(self.start_y, self.cur_y)
        self.rect_id = self.canvas.create_rectangle(
            x1 - self.vx, y1 - self.vy, x2 - self.vx, y2 - self.vy,
            outline="#00e5ff", width=2
        )

    def _release(self, event):
        if not self.selecting:
            return
        self.selecting = False
        x1, y1 = min(self.start_x, self.cur_x), min(self.start_y, self.cur_y)
        x2, y2 = max(self.start_x, self.cur_x), max(self.start_y, self.cur_y)
        if x2 - x1 < 8 or y2 - y1 < 8:
            self._cancel()
            return
        self.win.destroy()
        self.on_selected(x1, y1, x2, y2)

    def _cancel(self):
        self.win.destroy()
        self.on_cancel()


# ======================================================================
#  SCREENSHOT (foto)
# ======================================================================
def take_screenshot(parent, on_done):
    def _selected(x1, y1, x2, y2):
        # pequena pausa para asegurar que el overlay ya se cerro
        parent.after(120, lambda: _grab(x1, y1, x2, y2))

    def _grab(x1, y1, x2, y2):
        try:
            # all_screens=True permite capturar de CUALQUIER monitor
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
            copied = copy_image_to_clipboard(img)
            ImageOptionsPopup(parent, img, copied, on_done)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo capturar:\n{e}")
            on_done()

    RegionSelector(
        parent,
        "FOTO: arrastra con el clic izquierdo para seleccionar  ·  clic derecho para cancelar",
        _selected, on_done,
    )


class ImageOptionsPopup:
    def __init__(self, parent, image, copied_ok, on_done):
        self.parent = parent
        self.image = image
        self.on_done = on_done

        self.win = tk.Toplevel(parent)
        self.win.title("Screenshot listo")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#1e1e2e")

        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        preview = image.copy()
        preview.thumbnail((int(sw * 0.85), int(sh * 0.75)))
        photo = ImageTk.PhotoImage(preview)
        lbl = tk.Label(self.win, image=photo, bg="#1e1e2e", bd=2, relief=tk.SOLID)
        lbl.image = photo
        lbl.pack(pady=(12, 6), padx=12)

        if copied_ok:
            msg, color = "✅ Copiado (Ctrl+V para pegar)", "#00e676"
        else:
            msg, color = "Capturado (no se pudo copiar, usa Guardar)", "#ffb74d"
        info = tk.Frame(self.win, bg="#1e1e2e")
        info.pack()
        tk.Label(info, text=msg, font=("Arial", 9, "bold"), bg="#1e1e2e", fg=color).pack(side=tk.LEFT)
        tk.Label(info, text=f"   ·   {image.size[0]}x{image.size[1]} px",
                 font=("Arial", 8), bg="#1e1e2e", fg="#888").pack(side=tk.LEFT)

        btns = tk.Frame(self.win, bg="#1e1e2e")
        btns.pack(pady=(6, 12))

        def mkbtn(text, cmd, bg):
            tk.Button(btns, text=text, command=cmd, bg=bg, fg="white",
                      font=("Arial", 9, "bold"), relief=tk.FLAT,
                      padx=10, pady=5, cursor="hand2", activebackground=bg).pack(side=tk.LEFT, padx=4)

        mkbtn("📋 Copiar", self._recopy, "#3949ab")
        mkbtn("💾 Guardar", self._save, "#00897b")
        mkbtn("❌ Descartar", self._close, "#c62828")

        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        self.win.geometry(f"+{(sw - w)//2}+{(sh - h)//2}")
        self.win.protocol("WM_DELETE_WINDOW", self._close)

    def _recopy(self):
        if copy_image_to_clipboard(self.image):
            messagebox.showinfo("Copiado", "Listo. Pega con Ctrl+V donde quieras.")
        else:
            messagebox.showwarning("Aviso", "No se pudo copiar. Usa Guardar.")

    def _save(self):
        try:
            name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("Imagen PNG", "*.png"), ("Imagen JPG", "*.jpg")],
                initialfile=name,
            )
            if path:
                self.image.save(path)
                messagebox.showinfo("Guardado", f"Guardado en:\n{path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _close(self):
        self.win.destroy()
        self.on_done()


# ======================================================================
#  GRABACION DE VIDEO con FFmpeg (segmentos para poder pausar/reanudar)
# ======================================================================
class RecordingController:
    def __init__(self, ffmpeg, x, y, w, h):
        self.ffmpeg = ffmpeg
        # gdigrab + yuv420p necesita ancho/alto PAR
        self.x, self.y = x, y
        self.w = w if w % 2 == 0 else w - 1
        self.h = h if h % 2 == 0 else h - 1
        self.tempdir = tempfile.mkdtemp(prefix="procam_")
        self.segments = []
        self.proc = None
        self.seg_index = 0

    def _start_segment(self):
        seg = os.path.join(self.tempdir, f"seg_{self.seg_index}.mp4")
        self.seg_index += 1
        cmd = [
            self.ffmpeg, "-y",
            "-f", "gdigrab", "-framerate", "25",
            "-offset_x", str(self.x), "-offset_y", str(self.y),
            "-video_size", f"{self.w}x{self.h}",
            "-i", "desktop",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            seg,
        ]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
        self.segments.append(seg)

    def _stop_segment(self):
        if self.proc:
            try:
                # 'q' le dice a ffmpeg que termine limpio (mp4 valido)
                self.proc.communicate(input=b"q", timeout=6)
            except Exception:  # noqa: BLE001
                try:
                    self.proc.terminate()
                except Exception:  # noqa: BLE001
                    pass
            self.proc = None

    def start(self):
        self._start_segment()

    def pause(self):
        self._stop_segment()

    def resume(self):
        self._start_segment()

    def stop(self) -> str | None:
        self._stop_segment()
        return self._finalize()

    def _finalize(self) -> str | None:
        valid = [s for s in self.segments if os.path.exists(s) and os.path.getsize(s) > 0]
        if not valid:
            return None

        out_path = os.path.join(os.getenv("TEMP", self.tempdir), "procam_recording.mp4")
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                out_path = os.path.join(self.tempdir, "procam_recording.mp4")

        if len(valid) == 1:
            shutil.copyfile(valid[0], out_path)
            return out_path

        # Varios segmentos (hubo pausas): los unimos
        list_file = os.path.join(self.tempdir, "segments.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for s in valid:
                f.write(f"file '{s}'\n")
        try:
            subprocess.run(
                [self.ffmpeg, "-y", "-f", "concat", "-safe", "0",
                 "-i", list_file, "-c", "copy", out_path],
                check=True, creationflags=NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return out_path
        except Exception:  # noqa: BLE001
            # Si falla la union, al menos devolvemos el primer segmento
            shutil.copyfile(valid[0], out_path)
            return out_path

    def cleanup(self):
        try:
            shutil.rmtree(self.tempdir, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass


class RecordControlPanel:
    """Panel flotante con Comenzar / Pausar / Detener + cronometro."""

    def __init__(self, parent, app, ffmpeg, bbox, on_done):
        self.parent = parent
        self.app = app
        self.on_done = on_done
        x1, y1, x2, y2 = bbox
        self.ctrl = RecordingController(ffmpeg, x1, y1, x2 - x1, y2 - y1)
        self.state = "idle"          # idle | recording | paused
        self.elapsed = 0             # segundos
        self._timer_job = None

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#1e1e2e", highlightbackground="#3949ab", highlightthickness=2)

        # Cronometro
        self.time_lbl = tk.Label(self.win, text="00:00", font=("Consolas", 16, "bold"),
                                 bg="#1e1e2e", fg="#00e5ff")
        self.time_lbl.pack(side=tk.LEFT, padx=(12, 8), pady=8)

        self.dot = tk.Label(self.win, text="●", font=("Arial", 14), bg="#1e1e2e", fg="#555")
        self.dot.pack(side=tk.LEFT, padx=(0, 8))

        self.start_btn = tk.Button(self.win, text="▶ Comenzar", command=self.toggle_start_pause,
                                   bg="#00897b", fg="white", font=("Arial", 10, "bold"),
                                   relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        self.start_btn.pack(side=tk.LEFT, padx=4, pady=8)

        self.stop_btn = tk.Button(self.win, text="⏹ Detener", command=self.stop,
                                  bg="#c62828", fg="white", font=("Arial", 10, "bold"),
                                  relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        self.stop_btn.pack(side=tk.LEFT, padx=(4, 12), pady=8)

        # Posicion: arriba del area (o abajo si no hay espacio)
        self.win.update_idletasks()
        pw, ph = self.win.winfo_width(), self.win.winfo_height()
        px = x1
        py = y1 - ph - 8
        if py < 0:
            py = y2 + 8
        sw = self.win.winfo_screenwidth()
        if px + pw > sw:
            px = sw - pw - 10
        self.win.geometry(f"+{max(0, px)}+{max(0, py)}")

        # Atajos de teclado
        self.win.bind("<Return>", lambda e: self._enter_key())
        self.win.bind("<space>", lambda e: self._space_key())
        self.win.bind("<Escape>", lambda e: self.stop())
        self.win.focus_force()

    # ---- atajos ----
    def _enter_key(self):
        if self.state == "idle":
            self._begin()
        elif self.state == "paused":
            self._resume()

    def _space_key(self):
        if self.state == "recording":
            self._pause()
        elif self.state == "paused":
            self._resume()

    # ---- boton principal (Comenzar / Pausar / Reanudar) ----
    def toggle_start_pause(self):
        if self.state == "idle":
            self._begin()
        elif self.state == "recording":
            self._pause()
        elif self.state == "paused":
            self._resume()

    def _begin(self):
        self.ctrl.start()
        self.state = "recording"
        self.start_btn.config(text="⏸ Pausar", bg="#f9a825")
        self.dot.config(fg="#ff1744")
        self.app.set_recording_icon(True, self)
        self._tick()

    def _pause(self):
        self.ctrl.pause()
        self.state = "paused"
        self.start_btn.config(text="▶ Reanudar", bg="#00897b")
        self.dot.config(fg="#555")
        self._cancel_tick()

    def _resume(self):
        self.ctrl.resume()
        self.state = "recording"
        self.start_btn.config(text="⏸ Pausar", bg="#f9a825")
        self.dot.config(fg="#ff1744")
        self._tick()

    def stop(self):
        if self.state == "idle":
            # Nunca empezo: cancelar todo
            self._cancel_tick()
            self.ctrl.cleanup()
            self.win.destroy()
            self.app.set_recording_icon(False, None)
            self.on_done()
            return
        self._cancel_tick()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED, text="Procesando...")
        self.win.update()
        video_path = self.ctrl.stop()
        self.win.destroy()
        self.app.set_recording_icon(False, None)
        if video_path and os.path.exists(video_path):
            VideoOptionsPopup(self.parent, video_path, self.ctrl, self.on_done)
        else:
            messagebox.showwarning("Sin video", "No se grabo nada (grabacion muy corta).")
            self.ctrl.cleanup()
            self.on_done()

    # ---- cronometro ----
    def _tick(self):
        self.time_lbl.config(text=self._fmt(self.elapsed))
        self.elapsed += 1
        self._timer_job = self.parent.after(1000, self._tick)

    def _cancel_tick(self):
        if self._timer_job:
            self.parent.after_cancel(self._timer_job)
            self._timer_job = None

    @staticmethod
    def _fmt(secs):
        return f"{secs // 60:02d}:{secs % 60:02d}"


class VideoOptionsPopup:
    def __init__(self, parent, video_path, controller, on_done):
        self.parent = parent
        self.video_path = video_path
        self.controller = controller
        self.on_done = on_done

        self.win = tk.Toplevel(parent)
        self.win.title("Video listo")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#1e1e2e")

        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        tk.Label(self.win, text="🎬  Video grabado", font=("Arial", 14, "bold"),
                 bg="#1e1e2e", fg="white").pack(pady=(16, 4), padx=24)
        tk.Label(self.win, text=f"Tamano: {size_mb:.1f} MB",
                 font=("Arial", 9), bg="#1e1e2e", fg="#aaa").pack()

        # Botones para VER el video o ABRIR su carpeta (para arrastrarlo)
        top_btns = tk.Frame(self.win, bg="#1e1e2e")
        top_btns.pack(pady=(10, 6))
        tk.Button(top_btns, text="👁  Ver video", command=self._preview,
                  bg="#455a64", fg="white", font=("Arial", 9, "bold"),
                  relief=tk.FLAT, padx=10, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(top_btns, text="📁  Abrir carpeta", command=self._open_folder,
                  bg="#455a64", fg="white", font=("Arial", 9, "bold"),
                  relief=tk.FLAT, padx=10, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=4)

        btns = tk.Frame(self.win, bg="#1e1e2e")
        btns.pack(pady=(4, 16), padx=16)

        def mkbtn(text, cmd, bg):
            tk.Button(btns, text=text, command=cmd, bg=bg, fg="white",
                      font=("Arial", 9, "bold"), relief=tk.FLAT,
                      padx=10, pady=6, cursor="hand2", activebackground=bg).pack(side=tk.LEFT, padx=4)

        mkbtn("📋 Copiar archivo", self._copy, "#3949ab")
        mkbtn("💾 Guardar", self._save, "#00897b")
        mkbtn("❌ Descartar", self._discard, "#c62828")

        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        self.win.geometry(f"+{(sw - w)//2}+{(sh - h)//2}")
        self.win.protocol("WM_DELETE_WINDOW", self._discard)

    def _preview(self):
        try:
            os.startfile(self.video_path)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            messagebox.showinfo("Video", f"El video esta en:\n{self.video_path}")

    def _open_folder(self):
        """Abre el Explorador con el video seleccionado para arrastrarlo."""
        try:
            subprocess.Popen(["explorer", "/select,", self.video_path])
        except Exception:  # noqa: BLE001
            messagebox.showinfo("Carpeta", f"El video esta en:\n{self.video_path}")

    def _copy(self):
        if copy_file_to_clipboard(self.video_path):
            messagebox.showinfo(
                "Video copiado",
                "El video quedo copiado como ARCHIVO.\n\n"
                "• Pega con Ctrl+V en: WhatsApp/Telegram de escritorio, correo,\n"
                "  o en una carpeta del Explorador.\n\n"
                "⚠ En paginas web (chats del navegador) a veces NO se puede pegar\n"
                "un video. En ese caso usa '📁 Abrir carpeta' y ARRASTRA el archivo,\n"
                "o usa '💾 Guardar' y adjuntalo.",
            )
        else:
            messagebox.showwarning("Aviso", "No se pudo copiar. Usa Guardar.")

    def _save(self):
        try:
            name = f"grabacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("Video MP4", "*.mp4")],
                initialfile=name,
            )
            if path:
                shutil.copyfile(self.video_path, path)
                messagebox.showinfo("Guardado", f"Guardado en:\n{path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _discard(self):
        self.win.destroy()
        self.controller.cleanup()
        self.on_done()


def start_video_recording(parent, app, on_done):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        messagebox.showerror(
            "Falta FFmpeg",
            "No encontre FFmpeg (el motor que graba la pantalla).\n\n"
            "Ejecuta 'instalar_capturador.bat' para descargarlo automaticamente,\n"
            "o corre:  python download_ffmpeg.py",
        )
        on_done()
        return

    def _selected(x1, y1, x2, y2):
        RecordControlPanel(parent, app, ffmpeg, (x1, y1, x2, y2), on_done)

    RegionSelector(
        parent,
        "VIDEO: arrastra para elegir el area a grabar  ·  clic derecho para cancelar",
        _selected, on_done,
    )


# ======================================================================
#  App principal: icono en la bandeja del sistema
# ======================================================================
class ProCamApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.busy = False                 # evita abrir dos cosas a la vez
        self.active_recorder = None       # panel de grabacion activo (si hay)

        self.icon = pystray.Icon(
            "procam",
            make_tray_icon(False),
            "ProCam - clic: foto  ·  clic derecho: menu",
            menu=pystray.Menu(
                pystray.MenuItem("📸  Tomar screenshot", self._menu_screenshot, default=True),
                pystray.MenuItem("🎬  Grabar video", self._menu_video),
                pystray.MenuItem("❌  Salir", self._on_quit),
            ),
        )

    # ---- acciones del menu (vienen del hilo del icono) ----
    def _menu_screenshot(self, icon, item):
        # Si esta grabando, el clic izquierdo (accion default) DETIENE la grabacion
        if self.active_recorder is not None:
            self.root.after(0, self.active_recorder.stop)
            return
        self.root.after(0, self._do_screenshot)

    def _menu_video(self, icon, item):
        self.root.after(0, self._do_video)

    def _do_screenshot(self):
        if self.busy:
            return
        self.busy = True
        take_screenshot(self.root, on_done=self._free)

    def _do_video(self):
        if self.busy:
            return
        self.busy = True
        start_video_recording(self.root, self, on_done=self._free)

    def _free(self):
        self.busy = False

    # ---- icono rojo mientras graba ----
    def set_recording_icon(self, recording, recorder):
        self.active_recorder = recorder if recording else None
        try:
            self.icon.icon = make_tray_icon(recording)
            self.icon.title = ("ProCam - GRABANDO (clic para detener)"
                               if recording else
                               "ProCam - clic: foto  ·  clic derecho: menu")
        except Exception:  # noqa: BLE001
            pass

    def _on_quit(self, icon, item):
        icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    _enable_dpi_awareness()   # coordenadas correctas con varias pantallas
    ProCamApp().run()
