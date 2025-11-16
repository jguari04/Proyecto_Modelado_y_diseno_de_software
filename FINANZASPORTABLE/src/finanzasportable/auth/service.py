import json
import os
from typing import Dict, Optional
from .models import Usuario, Rol, TokenConfirmacion, EstadoCuenta

USERS_FILE = os.path.join(os.path.dirname(__file__), "users_db.json")

def cargar_usuarios() -> Dict[str, Usuario]:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        data = json.load(f)
    usuarios = {}
    for user_id, u in data.items():
        usuarios[user_id] = Usuario(
            id=user_id,
            nombre=u["nombre"],
            email=u["email"],
            password_hash=u["password_hash"],
            estado=EstadoCuenta(u["estado"]),
            roles=[Rol(nombre=r) for r in u.get("roles", [])]
        )
    return usuarios

def guardar_usuarios(usuarios: Dict[str, Usuario]):
    data = {}
    for user_id, u in usuarios.items():
        data[user_id] = {
            "nombre": u.nombre,
            "email": u.email,
            "password_hash": u.password_hash,
            "estado": u.estado.value,
            "roles": [r.nombre for r in u.roles]
        }
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

USUARIOS = cargar_usuarios()
TOKENS: Dict[str, TokenConfirmacion] = {}

def registrar_usuario(nombre: str, email: str, password: str) -> TokenConfirmacion:
    if any(u.email == email for u in USUARIOS.values()):
        raise ValueError("El email ya está registrado")

    user_id = f"user-{len(USUARIOS) + 1}"
    usuario = Usuario(
        id=user_id,
        nombre=nombre,
        email=email,
        password_hash=Usuario.hash_password(password),
        estado=EstadoCuenta.PENDIENTE,
    )
    USUARIOS[user_id] = usuario
    guardar_usuarios(USUARIOS)

    token = TokenConfirmacion.generar(usuario_id=user_id)
    TOKENS[token.token] = token
    return token

def confirmar_cuenta(token_str: str) -> Usuario:
    token = TOKENS.get(token_str)
    if not token:
        raise ValueError("Token inválido")

    if not token.es_valido():
        raise ValueError("Token expirado o ya utilizado")

    usuario = USUARIOS[token.usuario_id]
    usuario.estado = EstadoCuenta.ACTIVA
    token.usado = True
    guardar_usuarios(USUARIOS)
    return usuario

def login(email: str, password: str) -> Usuario:
    usuario: Optional[Usuario] = next(
        (u for u in USUARIOS.values() if u.email == email),
        None
    )
    if not usuario:
        raise ValueError("Credenciales inválidas")

    if usuario.estado != EstadoCuenta.ACTIVA:
        raise ValueError("La cuenta no está activa")

    if not usuario.verificar_password(password):
        raise ValueError("Credenciales inválidas")

    return usuario
