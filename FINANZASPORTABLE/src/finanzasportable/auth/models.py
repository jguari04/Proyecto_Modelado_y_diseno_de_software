from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from typing import List
import uuid
import hashlib


class EstadoCuenta(str, Enum):
  PENDIENTE = "pendiente"
  ACTIVA = "activa"
  BLOQUEADA = "bloqueada"


@dataclass
class Rol:
  nombre: str
  permisos: List[str] = field(default_factory=list)


@dataclass
class Usuario:
  id: str
  nombre: str
  email: str
  password_hash: str
  estado: EstadoCuenta = EstadoCuenta.PENDIENTE
  roles: List[Rol] = field(default_factory=list)

  @staticmethod
  def hash_password(password: str) -> str:
    # Hash simple para el TP (no usar en producción real)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

  def verificar_password(self, password: str) -> bool:
    return self.password_hash == self.hash_password(password)

  def tiene_permiso(self, permiso: str) -> bool:
    return any(permiso in r.permisos for r in self.roles)


@dataclass
class TokenConfirmacion:
  token: str
  usuario_id: str
  fecha_creacion: datetime
  fecha_vencimiento: datetime
  usado: bool = False

  @classmethod
  def generar(cls, usuario_id: str, horas_validez: int = 24) -> "TokenConfirmacion":
    ahora = datetime.utcnow()
    return cls(
      token=str(uuid.uuid4()),
      usuario_id=usuario_id,
      fecha_creacion=ahora,
      fecha_vencimiento=ahora + timedelta(hours=horas_validez),
    )

  def es_valido(self) -> bool:
    ahora = datetime.utcnow()
    return (not self.usado) and (self.fecha_creacion <= ahora <= self.fecha_vencimiento)
