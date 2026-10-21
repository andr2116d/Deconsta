"""Puertos del acceso: lo que los casos de uso necesitan del exterior, sin saber cómo se hace."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.datos_personales import DatosPersonales, TipoDocumento
from app.acceso.dominio.incorporacion import DocumentoLegal
from app.acceso.dominio.modelos import EventoAuditoria, Sesion, Usuario


class RepositorioUsuarios(Protocol):
    def por_nombre_usuario(self, nombre_usuario: str, *, bloquear: bool) -> Usuario | None:
        """bloquear=True toma la fila con FOR UPDATE: serializa los intentos simultáneos."""
        ...

    def por_id(self, usuario_id: UUID, *, bloquear: bool) -> Usuario | None: ...

    def existe_nombre_usuario(self, nombre_usuario: str) -> bool: ...

    def guardar(self, usuario: Usuario) -> None:
        """Persiste el estado de acceso: contraseña, indicadores, contador, bloqueo, eliminación y
        confirmación de datos."""
        ...

    def agregar(
        self, usuario: Usuario, datos: DatosPersonales, *, cargo: str | None = None
    ) -> None: ...

    def por_documento(self, tipo: TipoDocumento, numero: str) -> list[Usuario]:
        """Todas las cuentas con ese documento, incluidas las eliminadas, de la más reciente a la
        más antigua."""
        ...

    def asistentes_de(self, gerente_id: UUID) -> list[tuple[Usuario, FichaPersonal]]:
        """Asistentes no eliminadas del gerente, con sus datos descifrados."""
        ...

    def ficha(self, usuario_id: UUID) -> FichaPersonal | None:
        """Datos personales descifrados y el cargo de la cuenta."""
        ...

    def actualizar_datos(self, usuario_id: UUID, datos: DatosPersonales) -> None:
        """Reemplaza los datos personales. Lanza DatosDuplicados si el correo o el documento ya
        pertenecen a otra cuenta."""
        ...

    def cambiar_nombre_usuario(
        self, usuario_id: UUID, anterior: str, nuevo: str, ahora: datetime
    ) -> None:
        """Cambia el usuario y deja constancia del cambio. Lanza DatosDuplicados si está en uso."""
        ...

    def cambios_nombre_usuario_desde(self, usuario_id: UUID, desde: datetime) -> int: ...


class RepositorioSesiones(Protocol):
    def agregar(self, sesion: Sesion) -> None: ...

    def vigente(self, token_huella: bytes, ahora: datetime) -> Sesion | None: ...

    def revocar(self, sesion_id: UUID, ahora: datetime, motivo: str) -> None: ...

    def revocar_de_usuario(
        self, usuario_id: UUID, ahora: datetime, motivo: str, *, excepto: UUID | None = None
    ) -> int: ...


class RegistroAuditoria(Protocol):
    def registrar(self, evento: EventoAuditoria) -> None: ...


class RepositorioDocumentosLegales(Protocol):
    def vigentes(self, ahora: datetime) -> list[DocumentoLegal]:
        """La versión más alta de cada tipo cuya vigencia ya empezó."""
        ...

    def aceptaciones(self, usuario_id: UUID, documento_ids: list[int]) -> dict[int, datetime]:
        """Fecha en que la cuenta aceptó cada uno de esos documentos, si lo hizo."""
        ...

    def hay_sin_aceptar(self, usuario_id: UUID, ahora: datetime) -> bool: ...

    def registrar_aceptacion(self, usuario_id: UUID, documento_id: int, ahora: datetime) -> bool:
        """Registra la aceptación; False si ya existía (no se duplica)."""
        ...


class UnidadDeTrabajo(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def usuarios(self) -> RepositorioUsuarios: ...

    @property
    def sesiones(self) -> RepositorioSesiones: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...

    @property
    def documentos(self) -> RepositorioDocumentosLegales: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadDeTrabajo = Callable[[], UnidadDeTrabajo]
Reloj = Callable[[], datetime]


class ProtectorContrasenas(Protocol):
    def generar_hash(self, contrasena: str) -> str: ...

    def verificar(self, contrasena_hash: str, contrasena: str) -> bool: ...

    def necesita_rehash(self, contrasena_hash: str) -> bool: ...

    def simular_verificacion(self, contrasena: str) -> None:
        """Tarda lo mismo que verificar: un usuario inexistente no se delata por el tiempo."""
        ...


@dataclass(frozen=True)
class Cupo:
    permitido: bool
    reintentar_en: int


@dataclass(frozen=True)
class Limite:
    ambito: str
    maximo: int
    ventana_segundos: int


class LimitadorSolicitudes(Protocol):
    def consumir(self, limite: Limite, identificador: str) -> Cupo:
        """Cuenta una solicitud. Lanza ServicioNoDisponible si no puede comprobar el límite."""
        ...
