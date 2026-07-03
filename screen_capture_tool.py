#!/usr/bin/env python3
"""
Herramienta de captura de pantalla desde la BARRA DE TAREAS (Windows)

COMO FUNCIONA:
- El programa se pone como un iconito 📷 junto al reloj de Windows
  (abajo a la derecha, en la bandeja del sistema).
- CLIC en el icono  ->  entras en modo captura.
- Arrastras con el clic izquierdo para seleccionar la region.
- Al soltar, se toma el screenshot y se COPIA solo al portapapeles (Ctrl+V).
- Puedes GUARDARLO o solo pegarlo donde quieras.
- CLIC DERECHO en el icono  ->  menu (Tomar screenshot / Salir).

TODO CON EL MOUSE. La pantalla queda limpia (nada flotando encima).

Necesita: pip install pystray Pillow
"""

import os
import sys
import subprocess
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


# ----------------------------------------------------------------------
#  Icono de la bandeja (se dibuja una camarita simple)
# ----------------------------------------------------------------------
def make_tray_icon() -> Image.Image:
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # cuerpo de la camara
    d.rounded_rectangle([8, 20, 56, 52], radius=6, fill='#3949ab')
    # visor arriba
    d.rectangle([24, 14, 40, 22], fill='#3949ab')
    # lente
    d.ellipse([24, 28, 40, 44], fill='white')
    d.ellipse([28, 32, 36, 40], fill='#3949ab')
    # flash
    d.ellipse([46, 24, 52, 30], fill='white')
    return img


# ----------------------------------------------------------------------
#  Overlay para seleccionar la region con el mouse
# ----------------------------------------------------------------------
class CaptureOverlay:
    def __init__(self, parent, on_done):
        self.parent = parent
        self.on_done = on_done
        self.start_x = self.start_y = 0
        self.cur_x = self.cur_y = 0
        self.capturing = False
        self.rect_id = None
        self.screenshot_image = None

        self.win = tk.Toplevel(parent)
        self.win.attributes('-fullscreen', True)
        self.win.attributes('-alpha', 0.25)
        self.win.attributes('-topmost', True)
        self.win.configure(bg='black', cursor='crosshair')

        self.canvas = tk.Canvas(self.win, bg='black', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(
            self.win.winfo_screenwidth() // 2, 40,
            text="Arrastra con el clic izquierdo para seleccionar  ·  clic derecho para cancelar",
            fill="white", font=("Arial", 15, "bold")
        )

        self.canvas.bind('<Button-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<Button-3>', lambda e: self._cancel())
        self.win.bind('<Escape>', lambda e: self._cancel())

    def _press(self, event):
        self.capturing = True
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.cur_x, self.cur_y = self.start_x, self.start_y

    def _drag(self, event):
        if not self.capturing:
            return
        self.cur_x, self.cur_y = event.x_root, event.y_root
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        x1, y1 = min(self.start_x, self.cur_x), min(self.start_y, self.cur_y)
        x2, y2 = max(self.start_x, self.cur_x), max(self.start_y, self.cur_y)
        self.rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline='#00e5ff', width=2)

    def _release(self, event):
        if not self.capturing:
            return
        self.capturing = False
        x1, y1 = min(self.start_x, self.cur_x), min(self.start_y, self.cur_y)
        x2, y2 = max(self.start_x, self.cur_x), max(self.start_y, self.cur_y)
        if x2 - x1 < 8 or y2 - y1 < 8:
            self._cancel()
            return
        self.win.withdraw()
        self.win.update()
        self.parent.after(120, lambda: self._grab(x1, y1, x2, y2))

    def _cancel(self):
        self.win.destroy()
        self.on_done()

    def _grab(self, x1, y1, x2, y2):
        try:
            self.screenshot_image = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            copied = copy_to_clipboard(self.screenshot_image)
            self.win.destroy()
            OptionsPopup(self.parent, self.screenshot_image, copied, self.on_done)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo capturar:\n{e}")
            self.win.destroy()
            self.on_done()


# ----------------------------------------------------------------------
#  Popup con vista previa y opciones
# ----------------------------------------------------------------------
class OptionsPopup:
    def __init__(self, parent, image, copied_ok, on_done):
        self.parent = parent
        self.image = image
        self.on_done = on_done

        self.win = tk.Toplevel(parent)
        self.win.title("Screenshot listo")
        self.win.resizable(False, False)
        self.win.attributes('-topmost', True)
        self.win.configure(bg='#1e1e2e')

        # Vista previa GRANDE: la imagen se muestra lo mas grande posible
        # (hasta el 85% de la pantalla) para que la veas bien antes de decidir.
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        max_w = int(sw * 0.85)
        max_h = int(sh * 0.75)
        preview = image.copy()
        preview.thumbnail((max_w, max_h))
        photo = ImageTk.PhotoImage(preview)
        lbl = tk.Label(self.win, image=photo, bg='#1e1e2e', bd=2, relief=tk.SOLID)
        lbl.image = photo
        lbl.pack(pady=(12, 6), padx=12)

        # Mensaje e info: en una sola linea pequena
        if copied_ok:
            msg, color = "✅ Copiado (Ctrl+V para pegar)", "#00e676"
        else:
            msg, color = "Capturado (no se pudo copiar, usa Guardar)", "#ffb74d"
        info = tk.Frame(self.win, bg='#1e1e2e')
        info.pack()
        tk.Label(info, text=msg, font=("Arial", 9, "bold"), bg='#1e1e2e', fg=color).pack(side=tk.LEFT)
        tk.Label(info, text=f"   ·   {image.size[0]}x{image.size[1]} px",
                 font=("Arial", 8), bg='#1e1e2e', fg='#888').pack(side=tk.LEFT)

        # Botones PEQUENOS en una fila horizontal (ocupan poco espacio)
        btns = tk.Frame(self.win, bg='#1e1e2e')
        btns.pack(pady=(6, 12))

        def mkbtn(text, cmd, bg):
            tk.Button(btns, text=text, command=cmd, bg=bg, fg='white',
                      font=("Arial", 9, "bold"), relief=tk.FLAT,
                      padx=10, pady=5, cursor='hand2', activebackground=bg).pack(side=tk.LEFT, padx=4)

        mkbtn("📋 Copiar", self._recopy, "#3949ab")
        mkbtn("💾 Guardar", self._save, "#00897b")
        mkbtn("❌ Descartar", self._close, "#c62828")

        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = (self.win.winfo_screenwidth() // 2) - (w // 2)
        y = (self.win.winfo_screenheight() // 2) - (h // 2)
        self.win.geometry(f"+{x}+{y}")
        self.win.protocol("WM_DELETE_WINDOW", self._close)

    def _recopy(self):
        if copy_to_clipboard(self.image):
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


# ----------------------------------------------------------------------
#  Copiar al portapapeles de Windows
# ----------------------------------------------------------------------
def copy_to_clipboard(image) -> bool:
    if sys.platform != 'win32':
        return False
    try:
        temp_path = os.path.join(os.getenv('TEMP', os.getcwd()), 'screenshot_clip.png')
        image.save(temp_path, 'PNG')
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            f"$img=[System.Drawing.Image]::FromFile('{temp_path}'); "
            "[System.Windows.Forms.Clipboard]::SetImage($img); "
            "$img.Dispose()"
        )
        subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                       check=True, creationflags=0x08000000)
        return True
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------
#  App principal: icono en la bandeja del sistema (barra de tareas)
# ----------------------------------------------------------------------
class TrayCaptureApp:
    def __init__(self):
        # tkinter corre en el hilo principal (oculto).
        self.root = tk.Tk()
        self.root.withdraw()

        self.icon = pystray.Icon(
            "capturador",
            make_tray_icon(),
            "Capturador de pantalla (clic para capturar)",
            menu=pystray.Menu(
                pystray.MenuItem("📸  Tomar screenshot", self._on_capture, default=True),
                pystray.MenuItem("❌  Salir", self._on_quit),
            ),
        )

    def _on_capture(self, icon, item):
        # El callback viene del hilo del icono: pasamos la captura al hilo de tkinter.
        self.root.after(0, self._start_capture)

    def _start_capture(self):
        CaptureOverlay(self.root, on_done=lambda: None)

    def _on_quit(self, icon, item):
        icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        # El icono corre en un hilo aparte; tkinter en el principal.
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.root.mainloop()


if __name__ == "__main__":
    TrayCaptureApp().run()
