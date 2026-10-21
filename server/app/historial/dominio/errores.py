"""Errores del historial, con un código estable y un mensaje que dice qué corregir."""

from collections.abc import Mapping


class ErrorHistorial(Exception):
    codigo = "ERROR_HISTORIAL"
    mensaje = "No pudimos consultar el historial."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class FiltroInvalido(ErrorHistorial):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los filtros marcados."
