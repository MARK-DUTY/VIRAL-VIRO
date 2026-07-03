#!/usr/bin/env python3
"""
Herramienta de captura de pantalla 100% con el MOUSE (para Windows)

COMO FUNCIONA:
- Aparece un boton flotante  📸  en una esquina de tu pantalla (siempre visible).
- Le das UN CLIC al boton  ->  entras en modo captura.
- Arrastras con el clic izquierdo para seleccionar la region.
- Al soltar, se toma el screenshot y se COPIA solo al portapapeles (Ctrl+V).
- Puedes GUARDARLO o solo pegarlo donde quieras.

TODO CON EL MOUSE. No necesitas el teclado.
- Puedes ARRASTRAR el boton flotante para moverlo de lugar.
- CLIC DERECHO sobre el boton  ->  menu para cerrar el programa.
"""

import os
import sys
import subprocess
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab, ImageTk


class FloatingButton:
    """Boton flotante siempre visible que inicia la captura con un clic."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)          # sin bordes ni barra
        self.root.attributes('-topmost', True)     # siempre encima
        self.root.attributes('-alpha', 0.92)
        self.root.configure(bg='#3949ab')

        # Posicion inicial: esquina inferior derecha
        size = 62
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - size - 30
        y = sh - size - 80
        self.root.geometry(f"{size}x{size}+{x}+{y}")

        self.btn = tk.Label(
            self.root, text="📸", font=("Segoe UI Emoji", 24),
            bg='#3949ab', fg='white', cursor='hand2'
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

        # --- Interaccion con el mouse ---
        # Clic izquierdo: si no arrastraste, inicia captura; si arrastraste, mueve.
        self.btn.bind('<Button-1>', self._press)
        self.btn.bind('<B1-Motion>', self._drag)
        self.btn.bind('<ButtonRelease-1>', self._release)
        # Clic derecho: menu (cerrar)
        self.btn.bind('<Button-3>', self._menu)

        self._down_x = 0
        self._down_y = 0
        self._moved = False

        # Menu contextual (clic derecho)
        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="📸  Tomar screenshot", command=self.start_capture)
        self.ctx.add_separator()
        self.ctx.add_command(label="❌  Cerrar programa", command=self.root.destroy)

    def _press(self, event):
        self._down_x = event.x_root
        self._down_y = event.y_root
        self._moved = False

    def _drag(self, event):
        dx = event.x_root - self._down_x
        dy = event.y_root - self._down_y
        if abs(dx) > 4 or abs(dy) > 4:
            self._moved = True
            x = self.root.winfo_x() + (event.x_root - self._offset_x())
        # mover la ventana siguiendo el mouse
        if self._moved:
            self.root.geometry(f"+{event.x_root - 31}+{event.y_root - 31}")

    def _offset_x(self):
        return 31

    def _release(self, event):
        # Si NO se movio, fue un clic -> iniciar captura
        if not self._moved:
            self.start_capture()

    def _menu(self, event):
        try:
            self.ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx.grab_release()

    def start_capture(self):
        # Ocultar el boton mientras capturamos
        self.root.withdraw()
        CaptureOverlay(self.root, on_done=self._show_again)

    def _show_again(self):
        # Volver a mostrar el boton flotante para la siguiente captura
        self.root.deiconify()
        self.root.attributes('-topmost', True)

    def run(self):
        self.root.mainloop()


class CaptureOverlay:
    """Overlay a pantalla completa para seleccionar la region con el mouse."""

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
        self.canvas.bind('<Button-3>', lambda e: self._cancel())  # clic derecho = cancelar
        self.win.bind('<Escape>', lambda e: self._cancel())

    def _press(self, event):
        self.capturing = True
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.cur_x = self.start_x
        self.cur_y = self.start_y

    def _drag(self, event):
        if not self.capturing:
            return
        self.cur_x = event.x_root
        self.cur_y = event.y_root
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


class OptionsPopup:
    """Popup con la vista previa y opciones (copiar de nuevo / guardar / cerrar)."""

    def __init__(self, parent, image, copied_ok, on_done):
        self.parent = parent
        self.image = image
        self.on_done = on_done

        self.win = tk.Toplevel(parent)
        self.win.title("Screenshot listo")
        self.win.resizable(False, False)
        self.win.attributes('-topmost', True)
        self.win.configure(bg='#1e1e2e')

        preview = image.copy()
        preview.thumbnail((420, 220))
        photo = ImageTk.PhotoImage(preview)
        lbl = tk.Label(self.win, image=photo, bg='#1e1e2e')
        lbl.image = photo
        lbl.pack(pady=(16, 8), padx=16)

        if copied_ok:
            msg, color = "Ya esta COPIADO. Pega con Ctrl+V donde quieras.", "#00e676"
        else:
            msg, color = "Capturado. Usa Guardar (no se pudo copiar).", "#ffb74d"
        tk.Label(self.win, text=msg, font=("Arial", 11, "bold"), bg='#1e1e2e', fg=color).pack()
        tk.Label(self.win, text=f"{image.size[0]} x {image.size[1]} px",
                 font=("Arial", 9), bg='#1e1e2e', fg='#aaa').pack(pady=(2, 10))

        btns = tk.Frame(self.win, bg='#1e1e2e')
        btns.pack(pady=(0, 16), padx=16, fill=tk.X)

        def mkbtn(text, cmd, bg):
            b = tk.Button(btns, text=text, command=cmd, bg=bg, fg='white',
                          font=("Arial", 11, "bold"), relief=tk.FLAT,
                          padx=12, pady=10, cursor='hand2', activebackground=bg)
            b.pack(fill=tk.X, pady=4)

        mkbtn("📋  Copiar de nuevo (Ctrl+V)", self._recopy, "#3949ab")
        mkbtn("💾  Guardar en mi PC", self._save, "#00897b")
        mkbtn("✅  Listo (cerrar)", self._close, "#c62828")

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


def copy_to_clipboard(image) -> bool:
    """Copia la imagen al portapapeles de Windows (para pegar con Ctrl+V)."""
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


if __name__ == "__main__":
    FloatingButton().run()
