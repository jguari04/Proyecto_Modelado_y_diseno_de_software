"""
GUI de autenticación para Finanza.

- Registro de usuario
- Login

Después de login exitoso:
- Cierra esta ventana
- Lanza en OTRO proceso: `python -m app.gui_mp`
  usando el mismo intérprete (venv) y agregando ./src al PYTHONPATH.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

from finanzasportable.auth import registrar_usuario, confirmar_cuenta, login


def lanzar_gui_finanza():
    """
    Lanza la GUI principal de Finanza en otro proceso:
        python -m app.gui_mp

    Usa:
    - el mismo intérprete (sys.executable)
    - agrega ./src al PYTHONPATH
    """
    # Directorio raíz del proyecto (donde está este archivo dentro de app/)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(root_dir, "src")

    env = os.environ.copy()
    # Prepend ./src al PYTHONPATH
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [sys.executable, "-m", "app.gui_mp"]
    try:
        subprocess.Popen(cmd, env=env)
    except Exception as exc:
        print("[ERROR] No se pudo lanzar app.gui_mp:", exc)
        messagebox.showerror(
            "Error",
            f"No se pudo abrir la GUI principal (app.gui_mp):\n{exc}"
        )


class AuthApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Finanza - Control de acceso")
        self.geometry("400x260")
        self.resizable(False, False)

        self._frame_actual = None
        self.cambiar_a_login()

    def cambiar_frame(self, nuevo_frame_cls):
        if self._frame_actual is not None:
            self._frame_actual.destroy()
        self._frame_actual = nuevo_frame_cls(self)
        self._frame_actual.pack(fill="both", expand=True)

    def cambiar_a_login(self):
        self.cambiar_frame(LoginFrame)

    def cambiar_a_registro(self):
        self.cambiar_frame(RegistroFrame)

    def on_login_exitoso(self, usuario):
        """
        - Informa login OK
        - Cierra esta ventana
        - Lanza app.gui_mp en otro proceso
        """
        messagebox.showinfo(
            "Login OK",
            f"Usuario autenticado:\n{usuario.email}\n\n"
            "Se abrirá la GUI principal de Finanza."
        )
        # Cerramos esta ventana
        self.destroy()
        # Lanzamos la GUI principal
        lanzar_gui_finanza()


class LoginFrame(tk.Frame):
    def __init__(self, master: AuthApp) -> None:
        super().__init__(master)
        self.master = master

        tk.Label(self, text="Inicio de sesión Finanza", font=("Arial", 14, "bold")).pack(pady=10)

        form_frame = tk.Frame(self)
        form_frame.pack(pady=10)

        tk.Label(form_frame, text="Email:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form_frame, text="Contraseña:").grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.entry_email = tk.Entry(form_frame, width=30)
        self.entry_password = tk.Entry(form_frame, width=30, show="*")

        self.entry_email.grid(row=0, column=1, padx=5, pady=5)
        self.entry_password.grid(row=1, column=1, padx=5, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Iniciar sesión", command=self.do_login).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Registrarse", command=self.master.cambiar_a_registro).grid(row=0, column=1, padx=5)

    def do_login(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()

        if not email or not password:
            messagebox.showwarning("Datos incompletos", "Ingresá email y contraseña.")
            return

        try:
            usuario = login(email, password)
        except Exception as exc:
            messagebox.showerror("Error de login", str(exc))
            return

        self.master.on_login_exitoso(usuario)


class RegistroFrame(tk.Frame):
    def __init__(self, master: AuthApp) -> None:
        super().__init__(master)
        self.master = master

        tk.Label(self, text="Registro de usuario Finanza", font=("Arial", 14, "bold")).pack(pady=10)

        form_frame = tk.Frame(self)
        form_frame.pack(pady=10)

        tk.Label(form_frame, text="Nombre:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form_frame, text="Contraseña:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form_frame, text="Confirmar contraseña:").grid(row=3, column=0, sticky="e", padx=5, pady=5)

        self.entry_nombre = tk.Entry(form_frame, width=30)
        self.entry_email = tk.Entry(form_frame, width=30)
        self.entry_password = tk.Entry(form_frame, width=30, show="*")
        self.entry_password2 = tk.Entry(form_frame, width=30, show="*")

        self.entry_nombre.grid(row=0, column=1, padx=5, pady=5)
        self.entry_email.grid(row=1, column=1, padx=5, pady=5)
        self.entry_password.grid(row=2, column=1, padx=5, pady=5)
        self.entry_password2.grid(row=3, column=1, padx=5, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Crear cuenta", command=self.do_registro).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Volver a login", command=self.master.cambiar_a_login).grid(row=0, column=1, padx=5)

    def do_registro(self):
        nombre = self.entry_nombre.get().strip()
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()
        password2 = self.entry_password2.get().strip()

        if not nombre or not email or not password or not password2:
            messagebox.showwarning("Datos incompletos", "Completá todos los campos.")
            return

        if password != password2:
            messagebox.showwarning("Contraseña", "Las contraseñas no coinciden.")
            return

        try:
            token = registrar_usuario(nombre, email, password)
            # Para el TP, simulamos que el usuario hace clic en el enlace del mail:
            confirmar_cuenta(token.token)
        except Exception as exc:
            messagebox.showerror("Error al registrar", str(exc))
            return

        messagebox.showinfo(
            "Registro exitoso",
            "Cuenta creada y confirmada correctamente.\nAhora podés iniciar sesión."
        )
        self.master.cambiar_a_login()


def main():
    app = AuthApp()
    app.mainloop()


if __name__ == "__main__":
    main()
