#!/usr/bin/env python3
"""
Herramienta de captura de pantalla con el mouse (para Windows)

REEMPLAZA Ctrl+Shift+S:
- Presiona clic izquierdo + arrastra para seleccionar la region
- Al soltar, se toma el screenshot automaticamente
- Se COPIA solo al portapapeles (para pegar con Ctrl+V donde quieras)
- Ademas puedes GUARDARLO o DESCARTARLO

Funciona 100% independiente. No necesita ningun otro programa.
"""

import os
import sys
import subprocess
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab, ImageTk


class ScreenCaptureApp:
    def __init__(self):
        self.start_x = 0
        self.start_y = 0
        self.current_x = 0
        self.current_y = 0
        self.capturing = False
        self.screenshot_image = None

        # Ventana raiz invisible (controla el ciclo de vida de la app)
        self.root = tk.Tk()
        self.root.withdraw()

        # Overlay a pantalla completa, semi-transparente, para seleccionar
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.25)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black', cursor='crosshair')

        self.canvas = tk.Canvas(
            self.overlay, bg='black', cursor='crosshair', highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Texto de ayuda arriba
        self.canvas.create_text(
            self.overlay.winfo_screenwidth() // 2, 40,
            text="Arrastra con el clic izquierdo para seleccionar  ·  ESC para cancelar",
            fill="white", font=("Arial", 16, "bold")
        )

        # Eventos del mouse
        self.canvas.bind('<Button-1>', self.on_mouse_press)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_release)
        self.overlay.bind('<Escape>', lambda e: self.cancel_capture())

        self.rect_id = None

    def on_mouse_press(self, event):
        self.capturing = True
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.current_x = self.start_x
        self.current_y = self.start_y

    def on_mouse_drag(self, event):
        if not self.capturing:
            return
        self.current_x = event.x_root
        self.current_y = event.y_root

        if self.rect_id:
            self.canvas.delete(self.rect_id)

        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)

        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline='#00e5ff', width=2
        )

    def on_mouse_release(self, event):
        if not self.capturing:
            return
        self.capturing = False

        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)

        # Region demasiado pequena: reiniciamos (probablemente fue un clic)
        if x2 - x1 < 8 or y2 - y1 < 8:
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            self.rect_id = None
            return

        # Ocultamos el overlay ANTES de capturar (para que no salga en la foto)
        self.overlay.withdraw()
        self.overlay.update()
        self.root.after(120, lambda: self._grab_region(x1, y1, x2, y2))

    def _grab_region(self, x1, y1, x2, y2):
        try:
            self.screenshot_image = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            # Copiamos AL PORTAPAPELES automaticamente (listo para Ctrl+V)
            copied = self._copy_to_clipboard(self.screenshot_image)
            self.show_options_popup(copied)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo capturar:\n{e}")
            self.root.quit()

    def cancel_capture(self):
        self.capturing = False
        self.root.quit()

    # ------------------------------------------------------------------
    #  Copiar la imagen al portapapeles de Windows (para pegar con Ctrl+V)
    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, image) -> bool:
        if sys.platform != 'win32':
            return False
        try:
            temp_path = os.path.join(
                os.getenv('TEMP', os.getcwd()), 'screenshot_clip.png'
            )
            image.save(temp_path, 'PNG')
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                f"$img=[System.Drawing.Image]::FromFile('{temp_path}'); "
                "[System.Windows.Forms.Clipboard]::SetImage($img); "
                "$img.Dispose()"
            )
            subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps],
                check=True,
                creationflags=0x08000000,  # sin ventana
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    #  Popup de opciones despues de capturar
    # ------------------------------------------------------------------
    def show_options_popup(self, copied_ok: bool):
        popup = tk.Toplevel(self.root)
        popup.title("Screenshot listo")
        popup.resizable(False, False)
        popup.attributes('-topmost', True)
        popup.configure(bg='#1e1e2e')

        # Vista previa
        preview = self.screenshot_image.copy()
        preview.thumbnail((420, 220))
        photo = ImageTk.PhotoImage(preview)
        img_label = tk.Label(popup, image=photo, bg='#1e1e2e')
        img_label.image = photo
        img_label.pack(pady=(16, 8), padx=16)

        # Mensaje segun si se copio bien
        if copied_ok:
            msg = "Ya esta COPIADO. Pega con Ctrl+V donde quieras."
            color = "#00e676"
        else:
            msg = "Capturado. Usa Guardar (no se pudo copiar al portapapeles)."
            color = "#ffb74d"
        tk.Label(
            popup, text=msg, font=("Arial", 11, "bold"),
            bg='#1e1e2e', fg=color
        ).pack(pady=(0, 4))

        tk.Label(
            popup,
            text=f"{self.screenshot_image.size[0]} x {self.screenshot_image.size[1]} px",
            font=("Arial", 9), bg='#1e1e2e', fg='#aaa'
        ).pack(pady=(0, 10))

        btns = tk.Frame(popup, bg='#1e1e2e')
        btns.pack(pady=(0, 16), padx=16, fill=tk.X)

        def mkbtn(text, cmd, bg):
            b = tk.Button(
                btns, text=text, command=cmd, bg=bg, fg='white',
                font=("Arial", 11, "bold"), relief=tk.FLAT,
                padx=12, pady=10, cursor='hand2', activebackground=bg
            )
            b.pack(fill=tk.X, pady=4)
            return b

        mkbtn("📋  Copiar de nuevo (Ctrl+V)", self._recopy, "#3949ab")
        mkbtn("💾  Guardar en mi PC", self.save_screenshot, "#00897b")
        mkbtn("❌  Cerrar", lambda: self.root.quit(), "#c62828")

        # Centrar el popup
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)
        popup.geometry(f"+{x}+{y}")

        popup.protocol("WM_DELETE_WINDOW", lambda: self.root.quit())

    def _recopy(self):
        ok = self._copy_to_clipboard(self.screenshot_image)
        if ok:
            messagebox.showinfo("Copiado", "Listo. Pega con Ctrl+V donde quieras.")
        else:
            messagebox.showwarning("Aviso", "No se pudo copiar. Usa Guardar.")

    def save_screenshot(self):
        try:
            default_name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("Imagen PNG", "*.png"), ("Imagen JPG", "*.jpg")],
                initialfile=default_name,
            )
            if file_path:
                self.screenshot_image.save(file_path)
                messagebox.showinfo("Guardado", f"Guardado en:\n{file_path}")
                self.root.quit()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def run(self):
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    ScreenCaptureApp().run()
