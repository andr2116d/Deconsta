import hashlib
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

# Intentos fallidos con los que se bloquea la cuenta de una asistente.
MAXIMO_INTENTOS_FALLIDOS = 5

PATRON_NOMBRE_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{1,38}[a-z0-9]$")


class Rol(StrEnum):
    GERENTE = "gerente"
    ASISTENTE = "asistente"


class Accion(StrEnum):
    INGRESO_EXITOSO = "INGRESO_EXITOSO"
    INGRESO_FALLIDO = "INGRESO_FALLIDO"
    INGRESO_RECHAZADO = "INGRESO_RECHAZADO"
    CUENTA_BLOQUEADA = "CUENTA_BLOQUEADA"
    CUENTA_DESBLOQUEADA = "CUENTA_DESBLOQUEADA"
    CUENTA_CREADA = "CUENTA_CREADA"
    CONTRASENA_CAMBIADA = "CONTRASENA_CAMBIADA"
    CAMBIO_CONTRASENA_FALLIDO = "CAMBIO_CONTRASENA_FALLIDO"
    CIERRE_SESION = "CIERRE_SESION"
    DOCUMENTOS_ACEPTADOS = "DOCUMENTOS_ACEPTADOS"
    DATOS_PERSONALES_ACTUALIZADOS = "DATOS_PERSONALES_ACTUALIZADOS"
    DOCUMENTO_CAMBIADO = "DOCUMENTO_CAMBIADO"
    NOMBRE_USUARIO_CAMBIADO = "NOMBRE_USUARIO_CAMBIADO"
    CONFIRMACION_CONTRASENA_FALLIDA = "CONFIRMACION_CONTRASENA_FALLIDA"


REGLA_NOMBRE_USUARIO = (
    "Usa de 3 a 40 letras minúsculas, números, '.', '_' o '-', empezando y terminando en letra o "
    "número."
)


def normalizar_nombre_usuario(valor: str) -> str:
    """Forma canónica para comparar: sin espacios en los extremos, NFKC y en minúsculas."""
    return unicodedata.normalize("NFKC", valor).strip().lower()


def nombre_usuario_valido(valor: str) -> bool:
    return PATRON_NOMBRE_USUARIO.match(valor) is not None


@dataclass
class Usuario:
    id: UUID
    rol: Rol
    gerente_id: UUID | None
    nombre_usuario: str
    nombres: str
    contrasena_hash: str
    debe_cambiar_contrasena: bool
    contrasena_actualizada_en: datetime
    ultimo_ingreso_en: datetime | None
    intentos_fallidos: int
    bloqueada_en: datetime | None

    @property
    def bloqueada(self) -> bool:
        return self.bloqueada_en is not None

    @property
    def primer_ingreso(self) -> bool:
        return self.ultimo_ingreso_en is None

    def registrar_intento_fallido(self, ahora: datetime) -> bool:
        """Cuenta un intento fallido y devuelve True si con él la cuenta queda bloqueada.

        El contador persiste en la base, así que recargar la página o abrir otra sesión no lo
        reinicia. Solo se bloquean las asistentes; en los gerentes el contador solo deja constancia
        y su protección es la limitación de frecuencia.
        """
        if self.bloqueada:
            return False
        self.intentos_fallidos += 1
        if self.rol is Rol.ASISTENTE and self.intentos_fallidos >= MAXIMO_INTENTOS_FALLIDOS:
            self.bloqueada_en = ahora
            return True
        return False

    def registrar_ingreso(self, ahora: datetime) -> None:
        """Un ingreso correcto reinicia el contador de intentos fallidos."""
        self.intentos_fallidos = 0
        self.ultimo_ingreso_en = ahora

    def cambiar_contrasena(self, contrasena_hash: str, ahora: datetime) -> None:
        self.contrasena_hash = contrasena_hash
        self.contrasena_actualizada_en = ahora
        self.debe_cambiar_contrasena = False

    def desbloquear(self) -> None:
        self.bloqueada_en = None
        self.intentos_fallidos = 0


@dataclass(frozen=True)
class Sesion:
    id: UUID
    usuario_id: UUID
    token_huella: bytes
    creada_en: datetime
    expira_en: datetime


@dataclass(frozen=True)
class EventoAuditoria:
    accion: Accion
    actor_id: UUID | None = None
    cuenta_id: UUID | None = None
    motivo: str | None = None
    detalle: dict[str, Any] = field(default_factory=dict)


def huella_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def nueva_sesion(usuario_id: UUID, ahora: datetime, duracion: timedelta) -> tuple[str, Sesion]:
    """Genera un token aleatorio de 256 bits. Solo su huella se guarda; el token va a la cookie."""
    token = secrets.token_urlsafe(32)
    sesion = Sesion(uuid4(), usuario_id, huella_token(token), ahora, ahora + duracion)
    return token, sesion
