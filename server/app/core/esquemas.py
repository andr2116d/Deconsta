"""Base de los cuerpos que recibe la API.

Ningún texto admite caracteres de control ni invisibles. El carácter nulo hace fallar a Postgres
y los de formato (U+202E, el inversor de dirección; U+200B, el espacio de ancho cero) permiten
que un texto se vea distinto de lo que dice. Las contraseñas no se revisan: se comparan tal cual
y nunca se muestran.
"""

import re
from typing import Any

from pydantic import BaseModel, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

# Controles C0 y C1 (salvo tabulación y saltos de línea), marcas de dirección e invisibles.
CARACTERES_PROHIBIDOS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]"
)
MENSAJE = "Quita los caracteres invisibles o de control que tiene este texto."


def _revisar(valor: Any) -> Any:
    if isinstance(valor, str) and CARACTERES_PROHIBIDOS.search(valor):
        raise PydanticCustomError("caracteres_invalidos", MENSAJE)
    if isinstance(valor, list):
        for elemento in valor:
            _revisar(elemento)
    return valor


class Entrada(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def sin_caracteres_de_control(cls, valor: Any, info: ValidationInfo) -> Any:
        if info.field_name and info.field_name.startswith("contrasena"):
            return valor
        return _revisar(valor)
