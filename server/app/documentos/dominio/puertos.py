"""Puertos de los documentos: lo que los casos de uso necesitan del exterior."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.modelos import Rol
from app.acceso.dominio.puertos import RegistroAuditoria
from app.documentos.dominio.analisis import Metadatos
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import (
    DatosLeidos,
    DeudaDelDocumento,
    Documento,
    Lectura,
    TipoArchivo,
)
from app.notificaciones.dominio.puertos import RepositorioNotificaciones


class Almacen(Protocol):
    """Almacenamiento privado de los archivos. Quien lo implementa los guarda cifrados."""

    def guardar(self, clave: str, contenido: bytes, tipo: TipoArchivo) -> None: ...

    def leer(self, clave: str) -> bytes:
        """Lanza ErrorAlmacen si el archivo no existe o no se puede leer."""
        ...


class ErrorAlmacen(Exception):
    """El almacenamiento no respondió o el archivo no se pudo descifrar."""


@dataclass(frozen=True)
class Examen:
    paginas: int
    metadatos: Metadatos


class InspectorArchivos(Protocol):
    def examinar(self, contenido: bytes, tipo: TipoArchivo) -> Examen:
        """Cuenta las páginas y lee los metadatos. Lanza ArchivoInvalido si el archivo está
        dañado, PdfProtegido si tiene contraseña y DemasiadasPaginas si excede el máximo."""
        ...


class LectorTexto(Protocol):
    def leer(self, contenido: bytes, tipo: TipoArchivo) -> Lectura:
        """OCR del documento. Lanza ErrorLectura si no se pudo procesar el archivo."""
        ...


class ErrorLectura(Exception):
    """El motor de lectura no pudo procesar el archivo."""


@dataclass(frozen=True)
class CategoriaConocida:
    nombre: str
    descripcion: str | None


@dataclass(frozen=True)
class RevisionIa:
    legible: bool
    datos: DatosLeidos
    # autentico, dudoso o alterado.
    veredicto: str
    motivos: tuple[str, ...] = field(default=())


class RevisorIa(Protocol):
    def revisar(
        self,
        contenido: bytes,
        tipo: TipoArchivo,
        lectura: Lectura,
        categorias: list[CategoriaConocida],
    ) -> RevisionIa:
        """Lanza ErrorRevision si el modelo no respondió o no dio una respuesta usable."""
        ...


class ErrorRevision(Exception):
    """La revisión con IA no se pudo completar."""


class ColaAnalisis(Protocol):
    def encolar(self, documento_id: UUID) -> None:
        """Lanza ErrorCola si no se pudo encolar."""
        ...


class ErrorCola(Exception):
    """La cola de análisis no está disponible."""


class Huellero(Protocol):
    def huella(self, valor: str) -> bytes: ...


class RepositorioDocumentos(Protocol):
    def agregar(self, documento: Documento) -> None: ...

    def por_id(self, documento_id: UUID, *, bloquear: bool = False) -> Documento | None: ...

    def guardar(self, documento: Documento) -> None: ...

    def deuda_con_archivo(self, gerente_id: UUID, huella: bytes) -> DeudaDelDocumento | None:
        """La deuda del espacio que ya respalda un archivo con esa huella."""
        ...

    def deuda_con_clave(self, gerente_id: UUID, huella: bytes) -> DeudaDelDocumento | None: ...

    def resumen_deuda(self, deuda_id: UUID) -> DeudaDelDocumento | None: ...

    def deudas_con_numeros(
        self, gerente_id: UUID, huellas: set[bytes]
    ) -> list[tuple[DeudaDelDocumento, set[bytes]]]:
        """Deudas del espacio cuyo documento comparte alguno de esos números largos, con todos
        los números de su documento."""
        ...

    def categorias(self, gerente_id: UUID) -> list[CategoriaConocida]:
        """Las activas del espacio, para que la IA proponga una."""
        ...


class RepositorioBloqueos(Protocol):
    def vigente(self, asistente_id: UUID) -> Bloqueo | None: ...

    def vigentes_del_espacio(self, gerente_id: UUID) -> list[Bloqueo]: ...

    def registrar_intento(self, asistente_id: UUID, deuda_id: UUID, ahora: datetime) -> None: ...

    def contar_intentos(self, asistente_id: UUID, desde: datetime) -> int: ...

    def ultimo_levantamiento(self, asistente_id: UUID) -> datetime | None: ...

    def bloquear(self, bloqueo: Bloqueo) -> bool:
        """False si ya tenía un bloqueo vigente."""
        ...

    def levantar(self, bloqueo_id: UUID, levantado_por: UUID, ahora: datetime) -> None: ...


class RepositorioCuentas(Protocol):
    def rol_y_gerente(self, usuario_id: UUID) -> tuple[Rol, UUID | None] | None: ...

    def bloquear_cuenta(self, usuario_id: UUID) -> bool:
        """Toma la fila de la cuenta con FOR UPDATE: los intentos simultáneos de una misma
        asistente se cuentan uno tras otro."""
        ...

    def ficha(self, usuario_id: UUID) -> FichaPersonal | None: ...


class UnidadDocumentos(Protocol):
    """Transacción: al salir sin excepción confirma; con excepción revierte."""

    @property
    def documentos(self) -> RepositorioDocumentos: ...

    @property
    def bloqueos(self) -> RepositorioBloqueos: ...

    @property
    def cuentas(self) -> RepositorioCuentas: ...

    @property
    def notificaciones(self) -> RepositorioNotificaciones: ...

    @property
    def auditoria(self) -> RegistroAuditoria: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...


FabricaUnidadDocumentos = Callable[[], UnidadDocumentos]
