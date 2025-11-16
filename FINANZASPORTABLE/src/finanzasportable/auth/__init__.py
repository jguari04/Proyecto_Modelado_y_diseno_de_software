"""
Módulo de control de acceso para Finanza.

Clases principales:
- Usuario
- Rol
- TokenConfirmacion

Servicios principales:
- registrar_usuario
- confirmar_cuenta
- login
"""

from .models import Usuario, Rol, TokenConfirmacion, EstadoCuenta
from .service import registrar_usuario, confirmar_cuenta, login
