"""Reglas de «Mi cuenta»: qué datos puede cambiar la propia persona y con qué límites.

- Solo cuenta como cambio lo que difiere tras normalizar (espacios, mayúsculas del correo, etc.).
- El número de documento identifica a la persona titular y no se cambia. La única excepción es
  pasar de DNI a carné de extranjería (por ejemplo, al mudarse), y exige una confirmación expresa.
- El nombre en los recibos solo lo tiene el gerente, titular de las deudas.
- El correo y el documento sirven para identificar y recuperar la cuenta: cambiarlos pide la
  contraseña actual, igual que cambiar el nombre de usuario.
- El nombre de usuario se cambia como máximo tres veces por mes calendario, en la hora del negocio.
"""

from dataclasses import dataclass, fields
from datetime import datetime, tzinfo

from app.acceso.dominio.datos_personales import DatosPersonales, TipoDocumento
from app.acceso.dominio.errores import (
    CambioDocumentoSinConfirmar,
    DocumentoNoModificable,
    SinCambios,
    SinPermiso,
)
from app.acceso.dominio.modelos import Rol

MAXIMO_CAMBIOS_NOMBRE_USUARIO = 3

# Cambiarlos permite identificar o recuperar la cuenta: se confirman con la contraseña.
CAMPOS_SENSIBLES = frozenset({"correo", "tipo_documento", "numero_documento"})


@dataclass(frozen=True)
class FichaPersonal:
    datos: DatosPersonales
    cargo: str | None


@dataclass(frozen=True)
class CupoNombreUsuario:
    usados: int
    renueva_en: datetime
    maximo: int = MAXIMO_CAMBIOS_NOMBRE_USUARIO

    @property
    def restantes(self) -> int:
        return max(0, self.maximo - self.usados)


@dataclass(frozen=True)
class CambiosDatos:
    campos: tuple[str, ...]

    @property
    def cambia_documento(self) -> bool:
        return "tipo_documento" in self.campos

    @property
    def requiere_contrasena(self) -> bool:
        return not CAMPOS_SENSIBLES.isdisjoint(self.campos)


def periodo_mensual(ahora: datetime, zona: tzinfo) -> tuple[datetime, datetime]:
    """Inicio del mes en curso y del siguiente, en la zona del negocio."""
    local = ahora.astimezone(zona)
    inicio = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    siguiente = inicio.replace(year=inicio.year + inicio.month // 12, month=inicio.month % 12 + 1)
    return inicio, siguiente


def revisar_cambios(
    actual: DatosPersonales, nuevos: DatosPersonales, *, rol: Rol, confirmar_documento: bool
) -> CambiosDatos:
    """Devuelve los campos que cambian de verdad o rechaza los cambios que no se permiten."""
    if rol is not Rol.GERENTE and nuevos.nombre_recibos is not None:
        raise SinPermiso("Solo el gerente registra el nombre que figura en sus recibos.")
    campos = tuple(
        campo.name
        for campo in fields(DatosPersonales)
        if getattr(actual, campo.name) != getattr(nuevos, campo.name)
    )
    if not campos:
        raise SinCambios()
    if actual.tipo_documento is nuevos.tipo_documento:
        if "numero_documento" in campos:
            raise DocumentoNoModificable()
    elif (actual.tipo_documento, nuevos.tipo_documento) != (
        TipoDocumento.DNI,
        TipoDocumento.CARNE_EXTRANJERIA,
    ):
        raise DocumentoNoModificable()
    elif not confirmar_documento:
        raise CambioDocumentoSinConfirmar()
    return CambiosDatos(campos)
