"""Datos personales de una cuenta. Se validan y normalizan aquí; la infraestructura los cifra antes
de guardarlos y nunca los escribe en los registros."""

import re
from dataclasses import dataclass
from enum import StrEnum

from email_validator import EmailNotValidError, validate_email

from app.acceso.dominio.errores import DatosInvalidos

PATRON_NOMBRE = re.compile(r"^[^\W\d_]+(?:[ '’.-][^\W\d_]+)*$")
# Celular peruano: 9 dígitos que empiezan con 9 (Plan Técnico Fundamental de Numeración del MTC).
# Se acepta escrito con +51 o con separadores, y se guarda solo con los 9 dígitos.
PATRON_CELULAR = re.compile(r"^9\d{8}$")
MENSAJE_CELULAR = "Ingresa un celular peruano de 9 dígitos que empiece con 9."
LONGITUD_MAXIMA_CORREO = 254
LONGITUD_MAXIMA_NOMBRE = 80
# Como figura en un recibo: puede llevar números, comas o «&» (por ejemplo, una razón social).
PATRON_NOMBRE_RECIBOS = re.compile(r"^[^\W_](?:[\w .,&'’-]*[^\W_])?\.?$")
LONGITUD_MAXIMA_NOMBRE_RECIBOS = 120
PATRON_CARGO = re.compile(r"^[^\W\d_](?:[\w .,&()/'’-]*[^\W_])?\.?$")
LONGITUD_CARGO = (2, 80)


def normalizar_celular(valor: str) -> str:
    limpio = re.sub(r"[\s().-]", "", valor)
    if limpio.startswith("+51"):
        return limpio[3:]
    if len(limpio) == 11 and limpio.startswith("51"):
        return limpio[2:]
    return limpio


def _correo(valor: str, errores: dict[str, str]) -> str:
    """Comprueba la forma del correo (usuario, @ y dominio con extensión), sin enviar nada."""
    limpio = valor.strip()
    if "@" not in limpio:
        errores["correo"] = "Incluye la @ en tu correo, por ejemplo nombre@empresa.pe."
        return ""
    if len(limpio) > LONGITUD_MAXIMA_CORREO:
        errores["correo"] = f"Usa como máximo {LONGITUD_MAXIMA_CORREO} caracteres."
        return ""
    try:
        return validate_email(limpio, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        errores["correo"] = (
            "Revisa tu correo: necesita un usuario, la @ y un dominio con extensión, "
            "como nombre@empresa.pe."
        )
        return ""


class TipoDocumento(StrEnum):
    DNI = "dni"
    CARNE_EXTRANJERIA = "ce"


PATRONES_DOCUMENTO = {
    TipoDocumento.DNI: (re.compile(r"^\d{8}$"), "El DNI debe tener 8 dígitos."),
    TipoDocumento.CARNE_EXTRANJERIA: (
        re.compile(r"^[A-Z0-9]{9,12}$"),
        "El carné de extranjería debe tener entre 9 y 12 letras o dígitos.",
    ),
}


@dataclass(frozen=True)
class DatosPersonales:
    nombres: str
    apellidos: str
    # Puede faltar solo en una asistente recién registrada: lo completa al confirmar sus datos.
    correo: str | None
    tipo_documento: TipoDocumento
    numero_documento: str
    telefono: str | None = None
    # Solo del gerente: el titular de las deudas tal como aparece en sus recibos.
    nombre_recibos: str | None = None

    @classmethod
    def crear(
        cls,
        *,
        nombres: str,
        apellidos: str,
        correo: str | None,
        tipo_documento: str,
        numero_documento: str,
        telefono: str | None = None,
        nombre_recibos: str | None = None,
        correo_obligatorio: bool = True,
        telefono_obligatorio: bool = False,
    ) -> "DatosPersonales":
        errores: dict[str, str] = {}
        nombres_limpios = _nombre(nombres, "nombres", errores)
        apellidos_limpios = _nombre(apellidos, "apellidos", errores)
        correo_limpio: str | None = None
        if (correo or "").strip():
            correo_limpio = _correo(correo or "", errores)
        elif correo_obligatorio:
            errores["correo"] = "Ingresa tu correo."
        try:
            tipo = TipoDocumento(tipo_documento.strip().lower())
        except ValueError:
            errores["tipo_documento"] = "Elige DNI o carné de extranjería."
            tipo = TipoDocumento.DNI
        numero = re.sub(r"[\s-]", "", numero_documento).upper()
        patron, mensaje = PATRONES_DOCUMENTO[tipo]
        if "tipo_documento" not in errores and not patron.match(numero):
            errores["numero_documento"] = mensaje
        telefono_limpio = normalizar_celular(telefono) if telefono else None
        if telefono_limpio and not PATRON_CELULAR.match(telefono_limpio):
            errores["telefono"] = MENSAJE_CELULAR
        elif not telefono_limpio and telefono_obligatorio:
            errores["telefono"] = "Ingresa el número de celular."
        recibos = " ".join((nombre_recibos or "").split()) or None
        if recibos and (
            len(recibos) > LONGITUD_MAXIMA_NOMBRE_RECIBOS
            or not PATRON_NOMBRE_RECIBOS.match(recibos)
        ):
            errores["nombre_recibos"] = (
                f"Escríbelo como figura en tus recibos, hasta {LONGITUD_MAXIMA_NOMBRE_RECIBOS} "
                "caracteres."
            )
        if errores:
            raise DatosInvalidos(campos=errores)
        return cls(
            nombres_limpios,
            apellidos_limpios,
            correo_limpio,
            tipo,
            numero,
            telefono_limpio or None,
            recibos,
        )


def validar_cargo(cargo: str | None) -> str | None:
    """El cargo lo fija quien crea la cuenta; la persona no lo edita."""
    limpio = " ".join((cargo or "").split())
    if not limpio:
        return None
    minimo, maximo = LONGITUD_CARGO
    if not minimo <= len(limpio) <= maximo or not PATRON_CARGO.match(limpio):
        raise DatosInvalidos(
            campos={"cargo": f"Usa de {minimo} a {maximo} caracteres, empezando con una letra."}
        )
    return limpio


def _nombre(valor: str, campo: str, errores: dict[str, str]) -> str:
    limpio = " ".join(valor.split())
    if not limpio:
        errores[campo] = "Este campo es obligatorio."
    elif len(limpio) > LONGITUD_MAXIMA_NOMBRE or not PATRON_NOMBRE.match(limpio):
        errores[campo] = f"Usa solo letras, hasta {LONGITUD_MAXIMA_NOMBRE} caracteres."
    return limpio
