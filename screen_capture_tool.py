#!/usr/bin/env python3
"""
Herramienta de captura de pantalla con drag del mouse para VIRAL-VIRO
- Presiona clic izquierdo + arrastra para seleccionar región
- Al soltar, muestra popup con opciones: Subir/Guardar/Descartar
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import ImageGrab, ImageTk
import io
import threading
from datetime import datetime
import json
import os
import sys

class ScreenCaptureApp:
    def __init__(self):
        self.start_x = 0
        self.start_y = 0
        self.current_x = 0
        self.current_y = 0
        self.capturing = False
        self.screenshot_image = None
        self.screenshot_data = None
        
        # Crear ventana principal invisible
        self.root = tk.Tk()
        self.root.withdraw()
        
        # Crear canvas para overlay
        self.overlay_root = tk.Tk()
        self.overlay_root.attributes('-alpha', 0.3)
        self.overlay_root.attributes('-topmost', True)
        self.overlay_root.geometry(f"{self.overlay_root.winfo_screenwidth()}x{self.overlay_root.winfo_screenheight()}+0+0")
        self.overlay_root.configure(bg='black', cursor='crosshair')
        
        self.canvas = tk.Canvas(
            self.overlay_root,
            bg='black',
            cursor='crosshair',
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bindings para el overlay
        self.overlay_root.bind('<Button-1>', self.on_mouse_press)
        self.overlay_root.bind('<B1-Motion>', self.on_mouse_drag)
        self.overlay_root.bind('<ButtonRelease-1>', self.on_mouse_release)
        self.overlay_root.bind('<Escape>', lambda e: self.cancel_capture())
        
        # Rectangle ID para el selector visual
        self.rect_id = None
        
    def on_mouse_press(self, event):
        """Se ejecuta al presionar clic izquierdo"""
        self.capturing = True
        self.start_x = event.x_root - self.overlay_root.winfo_x()
        self.start_y = event.y_root - self.overlay_root.winfo_y()
        self.current_x = self.start_x
        self.current_y = self.start_y
        
    def on_mouse_drag(self, event):
        """Se ejecuta mientras se arrastra el mouse"""
        if not self.capturing:
            return
            
        self.current_x = event.x_root - self.overlay_root.winfo_x()
        self.current_y = event.y_root - self.overlay_root.winfo_y()
        
        # Redibujar el rectángulo
        self.canvas.delete(self.rect_id)
        
        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)
        
        # Dibujar rectángulo con borde blanco
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='white',
            width=2
        )
        
    def on_mouse_release(self, event):
        """Se ejecuta al soltar el clic"""
        if not self.capturing:
            return
            
        self.capturing = False
        
        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)
        
        # Validar que hay área seleccionada
        if x2 - x1 < 10 or y2 - y1 < 10:
            messagebox.showwarning("Advertencia", "Selecciona un área más grande")
            return
        
        # Cerrar overlay
        self.overlay_root.destroy()
        
        # Capturar la región seleccionada
        try:
            self.screenshot_image = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            self.screenshot_data = self.screenshot_image
            
            # Mostrar popup con opciones
            self.show_options_popup()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo capturar: {str(e)}")
            self.root.quit()
    
    def cancel_capture(self):
        """Cancela la captura (Escape)"""
        self.capturing = False
        self.overlay_root.destroy()
        self.root.quit()
    
    def show_options_popup(self):
        """Muestra popup con opciones después de capturar"""
        popup = tk.Toplevel(self.root)
        popup.title("Screenshot Capturado ✓")
        popup.geometry("500x450")
        popup.resizable(False, False)
        
        # Hacer que sea modal (siempre en primer plano)
        popup.attributes('-topmost', True)
        popup.configure(bg='#f0f0f0')
        
        # Centrar ventana en pantalla
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")
        
        # Título principal
        title_label = tk.Label(
            popup,
            text="✅ Screenshot Capturado",
            font=("Arial", 14, "bold"),
            bg='#f0f0f0',
            fg='#2c3e50'
        )
        title_label.pack(pady=10)
        
        # Mostrar vista previa
        if self.screenshot_image:
            # Redimensionar para vista previa
            preview = self.screenshot_image.copy()
            preview.thumbnail((420, 180))
            photo = ImageTk.PhotoImage(preview)
            
            preview_frame = tk.Frame(popup, bg='#f0f0f0', relief=tk.RIDGE, borderwidth=2)
            preview_frame.pack(pady=10, padx=20)
            
            preview_label = tk.Label(preview_frame, image=photo, bg='white')
            preview_label.image = photo  # Mantener referencia
            preview_label.pack()
        
        # Información con detalles
        info_text = f"Dimensiones: {self.screenshot_image.size[0]} × {self.screenshot_image.size[1]} px\nTiempo: {datetime.now().strftime('%H:%M:%S')}"
        info_label = tk.Label(
            popup,
            text=info_text,
            font=("Arial", 9),
            bg='#f0f0f0',
            fg='#555'
        )
        info_label.pack(pady=5)
        
        # Separador visual
        separator = tk.Frame(popup, bg='#ddd', height=2)
        separator.pack(fill=tk.X, padx=10, pady=10)
        
        # Frame de botones con mejor diseño
        button_frame = tk.Frame(popup, bg='#f0f0f0')
        button_frame.pack(pady=15, fill=tk.BOTH, expand=True)
        
        # Botón: Subir a VIRAL-VIRO (PRINCIPAL)
        upload_btn = tk.Button(
            button_frame,
            text="📤  Subir a VIRAL-VIRO",
            command=self.upload_to_viral_viro,
            bg="#27ae60",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=15,
            pady=12,
            relief=tk.RAISED,
            cursor="hand2"
        )
        upload_btn.pack(fill=tk.X, padx=20, pady=8)
        
        # Botón: Guardar
        save_btn = tk.Button(
            button_frame,
            text="💾  Guardar en PC",
            command=self.save_screenshot,
            bg="#3498db",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=15,
            pady=12,
            relief=tk.RAISED,
            cursor="hand2"
        )
        save_btn.pack(fill=tk.X, padx=20, pady=8)
        
        # Botón: Descartar
        discard_btn = tk.Button(
            button_frame,
            text="❌  Descartar",
            command=lambda: self.discard_screenshot(popup),
            bg="#e74c3c",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=15,
            pady=12,
            relief=tk.RAISED,
            cursor="hand2"
        )
        discard_btn.pack(fill=tk.X, padx=20, pady=8)
        
        # Agregar hover effects
        for btn in [upload_btn, save_btn, discard_btn]:
            btn.bind("<Enter>", lambda e, b=btn: self.on_button_enter(b))
            btn.bind("<Leave>", lambda e, b=btn: self.on_button_leave(b))
        
        popup.mainloop()
    
    def on_button_enter(self, button):
        """Efecto hover en botones"""
        button.config(relief=tk.SUNKEN)
    
    def on_button_leave(self, button):
        """Efecto hover off en botones"""
        button.config(relief=tk.RAISED)
    
    def upload_to_viral_viro(self):
        """Sube el screenshot a VIRAL-VIRO (cargándolo en clipboard)"""
        try:
            # Guardar en clipboard para que VIRAL-VIRO lo pegue
            import subprocess
            
            # Convertir a bytes y copiar al clipboard
            if sys.platform == 'win32':
                # En Windows, usar archivo temporal para clipboard
                temp_path = os.path.join(os.getenv('TEMP'), 'viral_viro_screenshot.png')
                self.screenshot_image.save(temp_path, 'PNG')
                
                # Copiar al clipboard usando PowerShell
                ps_script = f"""
                [Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms')
                $img = [System.Drawing.Image]::FromFile('{temp_path}')
                [System.Windows.Forms.Clipboard]::SetImage($img)
                """
                subprocess.run(['powershell', '-Command', ps_script], check=True)
                
                messagebox.showinfo(
                    "✅ Éxito",
                    "Screenshot copiado al clipboard.\n\nAhora pega en VIRAL-VIRO con Ctrl+V"
                )
            else:
                messagebox.showerror("Error", "Esta función solo funciona en Windows")
            
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Error al subir", f"No se pudo subir: {str(e)}")
    
    def save_screenshot(self):
        """Guarda el screenshot en el disco"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
                initialfile=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            
            if file_path:
                self.screenshot_image.save(file_path)
                messagebox.showinfo("✅ Guardado", f"Guardado en:\n{file_path}")
                self.root.quit()
        except Exception as e:
            messagebox.showerror("Error al guardar", f"No se pudo guardar: {str(e)}")
    
    def discard_screenshot(self, popup):
        """Descarta el screenshot y permite capturar otro"""
        popup.destroy()
        self.screenshot_image = None
        self.screenshot_data = None
        
        # Reiniciar captura
        messagebox.showinfo("Descartado", "Screenshot descartado. Abre el programa de nuevo para capturar.")
        self.root.quit()
    
    def run(self):
        """Inicia la aplicación"""
        try:
            self.overlay_root.mainloop()
        except Exception as e:
            messagebox.showerror("Error fatal", str(e))
        finally:
            self.root.destroy()

if __name__ == "__main__":
    app = ScreenCaptureApp()
    app.run()
