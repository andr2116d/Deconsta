"""Datos personales de una cuenta. Se validan y normalizan aquí; la infraestructura los cifra antes
de guardarlos y nunca los escribe en los registros."""

import re
from dataclasses import dataclass
from enum import StrEnum

from email_validator import EmailNotValidError, validate_email

from app.acceso.dominio.errores import DatosInvalidos

PATRON_NOMBRE = re.compile(r"^[^\W\d_]+(?:[ '’.-][^\W\d_]+)*$")
PATRON_TELEFONO = re.compile(r"^\+?\d{9,15}$")
LONGITUD_MAXIMA_NOMBRE = 80


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
    correo: str
    tipo_documento: TipoDocumento
    numero_documento: str
    telefono: str | None = None

    @classmethod
    def crear(
        cls,
        *,
        nombres: str,
        apellidos: str,
        correo: str,
        tipo_documento: str,
        numero_documento: str,
        telefono: str | None = None,
    ) -> "DatosPersonales":
        errores: dict[str, str] = {}
        nombres_limpios = _nombre(nombres, "nombres", errores)
        apellidos_limpios = _nombre(apellidos, "apellidos", errores)
        try:
            correo_limpio = validate_email(correo.strip(), check_deliverability=False).normalized
            correo_limpio = correo_limpio.lower()
        except EmailNotValidError:
            errores["correo"] = "Ingresa un correo válido."
            correo_limpio = ""
        try:
            tipo = TipoDocumento(tipo_documento.strip().lower())
        except ValueError:
            errores["tipo_documento"] = "Elige DNI o carné de extranjería."
            tipo = TipoDocumento.DNI
        numero = re.sub(r"[\s-]", "", numero_documento).upper()
        patron, mensaje = PATRONES_DOCUMENTO[tipo]
        if "tipo_documento" not in errores and not patron.match(numero):
            errores["numero_documento"] = mensaje
        telefono_limpio = re.sub(r"[\s()-]", "", telefono) if telefono else None
        if telefono_limpio and not PATRON_TELEFONO.match(telefono_limpio):
            errores["telefono"] = "Ingresa un teléfono de 9 a 15 dígitos."
        if errores:
            raise DatosInvalidos(campos=errores)
        return cls(
            nombres_limpios, apellidos_limpios, correo_limpio, tipo, numero, telefono_limpio or None
        )


def _nombre(valor: str, campo: str, errores: dict[str, str]) -> str:
    limpio = " ".join(valor.split())
    if not limpio:
        errores[campo] = "Este campo es obligatorio."
    elif len(limpio) > LONGITUD_MAXIMA_NOMBRE or not PATRON_NOMBRE.match(limpio):
        errores[campo] = f"Usa solo letras, hasta {LONGITUD_MAXIMA_NOMBRE} caracteres."
    return limpio
