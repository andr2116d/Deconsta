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


class CausaBloqueo(StrEnum):
    INTENTOS_FALLIDOS = "intentos_fallidos"
    GERENTE = "gerente"


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
    CUENTA_ELIMINADA = "CUENTA_ELIMINADA"
    CUENTA_RECUPERADA = "CUENTA_RECUPERADA"
    CONTRASENA_RESTABLECIDA = "CONTRASENA_RESTABLECIDA"
    DATOS_CONFIRMADOS = "DATOS_CONFIRMADOS"
    CATEGORIA_CREADA = "CATEGORIA_CREADA"
    CATEGORIA_EDITADA = "CATEGORIA_EDITADA"
    CATEGORIA_ARCHIVADA = "CATEGORIA_ARCHIVADA"
    CATEGORIA_REACTIVADA = "CATEGORIA_REACTIVADA"
    LIMITE_AUTORIZACION_CAMBIADO = "LIMITE_AUTORIZACION_CAMBIADO"
    TITULAR_AUTORIZADO_AGREGADO = "TITULAR_AUTORIZADO_AGREGADO"
    TITULAR_AUTORIZADO_EDITADO = "TITULAR_AUTORIZADO_EDITADO"
    TITULAR_AUTORIZADO_QUITADO = "TITULAR_AUTORIZADO_QUITADO"
    DOCUMENTO_REPETIDO = "DOCUMENTO_REPETIDO"
    REGISTRO_DEUDAS_BLOQUEADO = "REGISTRO_DEUDAS_BLOQUEADO"
    REGISTRO_DEUDAS_DESBLOQUEADO = "REGISTRO_DEUDAS_DESBLOQUEADO"
    DEUDA_REGISTRADA = "DEUDA_REGISTRADA"
    DEUDA_AUTORIZADA = "DEUDA_AUTORIZADA"
    DEUDA_RECHAZADA = "DEUDA_RECHAZADA"
    DEUDA_REVISADA = "DEUDA_REVISADA"
    DEUDA_ANULADA = "DEUDA_ANULADA"
    COMPROBANTE_RECHAZADO = "COMPROBANTE_RECHAZADO"
    REGISTRO_PAGOS_BLOQUEADO = "REGISTRO_PAGOS_BLOQUEADO"
    REGISTRO_PAGOS_DESBLOQUEADO = "REGISTRO_PAGOS_DESBLOQUEADO"
    PAGO_REGISTRADO = "PAGO_REGISTRADO"


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
    causa_bloqueo: CausaBloqueo | None = None
    # Baja lógica: la cuenta no ingresa ni aparece en el equipo, pero su historial se conserva.
    eliminada_en: datetime | None = None
    # Una asistente recién registrada (o recuperada) confirma sus datos en su primer ingreso.
    datos_confirmados_en: datetime | None = None

    @property
    def bloqueada(self) -> bool:
        return self.bloqueada_en is not None

    @property
    def eliminada(self) -> bool:
        return self.eliminada_en is not None

    @property
    def debe_confirmar_datos(self) -> bool:
        return self.rol is Rol.ASISTENTE and self.datos_confirmados_en is None

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
            self.causa_bloqueo = CausaBloqueo.INTENTOS_FALLIDOS
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
        self.causa_bloqueo = None
        self.intentos_fallidos = 0

    def bloquear_por_gerente(self, ahora: datetime) -> None:
        self.bloqueada_en = ahora
        self.causa_bloqueo = CausaBloqueo.GERENTE

    def eliminar(self, ahora: datetime) -> None:
        self.eliminada_en = ahora

    def restablecer_contrasena(self, contrasena_hash: str, ahora: datetime) -> None:
        """Su gerente le entrega una contraseña temporal nueva: deberá cambiarla al ingresar. El
        bloqueo no cambia; se levanta aparte."""
        self.cambiar_contrasena(contrasena_hash, ahora)
        self.debe_cambiar_contrasena = True
        if not self.bloqueada:
            self.intentos_fallidos = 0

    def recuperar(self, contrasena_hash: str, ahora: datetime) -> None:
        """Vuelve al equipo como recién registrada: contraseña temporal nueva, sin bloqueo y con
        sus datos por confirmar."""
        self.eliminada_en = None
        self.desbloquear()
        self.cambiar_contrasena(contrasena_hash, ahora)
        self.debe_cambiar_contrasena = True
        self.datos_confirmados_en = None

    def confirmar_datos(self, ahora: datetime) -> None:
        self.datos_confirmados_en = ahora


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
