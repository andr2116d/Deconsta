"""Importes en soles (PEN), la única moneda de Deconsta. Se manejan como Decimal con dos decimales:
nunca como float, para no perder céntimos al comparar con el límite."""

import re
from decimal import Decimal

IMPORTE_MAXIMO = Decimal("9999999.99")
# Sin separador de miles: el cliente envía «2900.50». Se aceptan coma o punto como decimal.
PATRON_IMPORTE = re.compile(r"^\d{1,7}(?:[.,]\d{1,2})?$")


def error_importe(valor: str) -> str | None:
    limpio = valor.strip()
    if not limpio:
        return "Escribe el importe en soles."
    if not PATRON_IMPORTE.match(limpio):
        return "Escribe un importe en soles con hasta dos decimales, por ejemplo 2900.50."
    importe = Decimal(limpio.replace(",", "."))
    if importe <= 0:
        return "El importe debe ser mayor que cero."
    if importe > IMPORTE_MAXIMO:
        return f"El importe no puede superar {formatear_soles(IMPORTE_MAXIMO)}."
    return None


def a_importe(valor: str) -> Decimal:
    """Convierte un importe ya validado con error_importe."""
    return Decimal(valor.strip().replace(",", ".")).quantize(Decimal("0.01"))


def formatear_soles(importe: Decimal) -> str:
    """Como se lee en Perú: «S/ 2,900.50»."""
    return f"S/ {importe:,.2f}"
