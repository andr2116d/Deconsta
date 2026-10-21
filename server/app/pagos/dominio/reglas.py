"""Reglas del análisis de un comprobante de pago.

Se reutilizan las capas del análisis de documentos (lectura, revisión con IA y metadatos) y lo
leído se compara con la cuota que dice pagar. A la IA no se le dice qué se espera: lee el
comprobante a ciegas y la comparación la hace el dominio.

- Ilegible: no se lee el texto, el importe o la fecha. Se sube una foto mejor; no cuenta para el
  bloqueo del registro de pagos.
- Rechazado (riesgo alto): no es un comprobante, otra moneda, fecha futura o anterior al registro
  de la deuda, otro código de pago, un importe que no es el de la cuota o señales de alteración.
  Cuenta para el bloqueo, salvo la posible mora: una deuda vencida pagada con más.
- Con riesgo medio el comprobante sirve, pero baja la confianza que ve el gerente: otra empresa,
  otro titular, un lugar que no se marcó en la deuda, sin número de operación, datos que no
  aparecen en el texto leído.

En un agente, un voucher por menos que la cuota vale si los demás vouchers del mismo día completan
la cuota: eso se comprueba al registrar el pago.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.deudas.dominio.modelos import LugarPago
from app.documentos.dominio.analisis import (
    CONFIANZA_MINIMA,
    MINIMO_CARACTERES,
    importes_en_texto,
    normalizar_numero,
)
from app.documentos.dominio.modelos import Capa, Lectura, Riesgo, Senal
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    DatosComprobante,
    EstadoComprobante,
    Moneda,
)
from app.reglas.dominio.importes import formatear_soles

# Lo que impide revisar el comprobante: se pide una foto mejor.
ILEGIBLES = frozenset({"COMPROBANTE_ILEGIBLE", "SIN_IMPORTE", "SIN_FECHA"})
# Con riesgo alto, pero no es un intento de pasar un comprobante que no corresponde.
NO_CUENTAN = frozenset({"POSIBLE_MORA"})
# Palabras que no distinguen a una empresa: «Hidrandina S.A.» y «HIDRANDINA» son la misma.
PALABRAS_SOCIETARIAS = frozenset(
    {"sa", "saa", "sac", "srl", "eirl", "sociedad", "anonima", "abierta", "cerrada", "empresa",
     "de", "del", "la", "las", "los", "y", "peru", "servicios", "distribucion", "electrica"}
)  # fmt: skip
MINIMO_CODIGO_PARCIAL = 6
# Comprobantes que no corresponden en 24 horas antes de bloquear el registro de pagos.
MAXIMO_RECHAZADOS = 3
# Vouchers de un mismo pago: un agente lo cobra por partes.
MAXIMO_COMPROBANTES = 5


@dataclass(frozen=True)
class CuotaEsperada:
    """Lo que debería decir el comprobante: la cuota y la deuda que dice pagar."""

    importe: Decimal
    codigo_pago: str | None
    # La empresa que emitió el documento de la deuda, si se leyó.
    empresa: str | None
    titular: str | None
    lugares: tuple[LugarPago, ...]
    # El día en que se registró la deuda, en la zona del espacio.
    registrada_el: date
    vencida: bool


def _senal(capa: Capa, codigo: str, detalle: str, riesgo: Riesgo) -> Senal:
    return Senal(capa, codigo, detalle, riesgo)


def senal_ilegible() -> Senal:
    return _senal(
        Capa.LECTURA,
        "COMPROBANTE_ILEGIBLE",
        "No pudimos leer el comprobante. Sube una foto nítida, completa y con buena luz, o la "
        "captura original de la operación.",
        Riesgo.ALTO,
    )


def senal_legibilidad(lectura: Lectura) -> Senal | None:
    caracteres = sum(c.isalnum() for c in lectura.texto)
    if caracteres >= MINIMO_CARACTERES and lectura.confianza >= CONFIANZA_MINIMA:
        return None
    return senal_ilegible()


def _alfanumerico(valor: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", valor.upper())


def _palabras(nombre: str) -> set[str]:
    plano = "".join(
        c for c in unicodedata.normalize("NFKD", nombre.casefold()) if not unicodedata.combining(c)
    )
    return {p for p in re.findall(r"[a-z0-9]+", plano) if len(p) >= 3} - PALABRAS_SOCIETARIAS


def mismo_nombre(uno: str, otro: str) -> bool:
    """Comparten alguna palabra que distingue: «Pluz Energía Perú» y «PLUZ ENERGIA»."""
    return bool(_palabras(uno) & _palabras(otro))


def mismo_codigo(leido: str, esperado: str) -> bool:
    """Iguales, o uno contiene al otro si el más corto tiene al menos seis caracteres: un voucher
    puede mostrar «54871236-0» para el suministro 54871236."""
    a, b = normalizar_numero(leido), normalizar_numero(esperado)
    if a == b:
        return True
    corto, largo = sorted((a, b), key=len)
    return len(corto) >= MINIMO_CODIGO_PARCIAL and corto in largo


def _importe(senales: list[Senal], datos: DatosComprobante, esperada: CuotaEsperada) -> None:
    importe = datos.importe
    assert importe is not None
    pagado, cuota = formatear_soles(importe), formatear_soles(esperada.importe)
    if importe < esperada.importe:
        if datos.lugar is LugarPago.AGENTE:
            senales.append(
                _senal(
                    Capa.IA,
                    "PAGO_PARCIAL",
                    f"Este voucher paga {pagado} de {cuota}. Si el agente te lo cobró por partes, "
                    "sube los otros vouchers del mismo día: juntos deben sumar la cuota.",
                    Riesgo.BAJO,
                )
            )
            return
        senales.append(
            _senal(
                Capa.IA,
                "MONTO_MENOR",
                f"El voucher paga {pagado} y la cuota es {cuota}. Sube el comprobante del pago "
                "completo de esta cuota.",
                Riesgo.ALTO,
            )
        )
    elif importe > esperada.importe:
        diferencia = formatear_soles(importe - esperada.importe)
        if esperada.vencida:
            senales.append(
                _senal(
                    Capa.IA,
                    "POSIBLE_MORA",
                    f"El voucher paga {pagado}, {diferencia} más que la cuota. Como la deuda está "
                    "vencida, puede ser mora. Por ahora no se registra un pago con mora: avísale "
                    "a tu gerente.",
                    Riesgo.ALTO,
                )
            )
            return
        senales.append(
            _senal(
                Capa.IA,
                "MONTO_MAYOR",
                f"El voucher paga {pagado} y la cuota es {cuota}. Si incluye una comisión, debe "
                "figurar aparte en el voucher.",
                Riesgo.ALTO,
            )
        )


def _codigo(
    senales: list[Senal], datos: DatosComprobante, lectura: Lectura, esperada: CuotaEsperada
) -> None:
    esperado = esperada.codigo_pago
    if not esperado:
        return
    # Si el texto leído trae el código de la deuda, la IA lo leyó mal o no lo vio: vale.
    if _alfanumerico(esperado) in _alfanumerico(lectura.texto):
        return
    if not datos.codigo_pago:
        senales.append(
            _senal(
                Capa.IA,
                "SIN_CODIGO",
                "El voucher no muestra el código de pago o suministro: no pudimos confirmar que "
                "sea de esta deuda.",
                Riesgo.MEDIO,
            )
        )
    elif not mismo_codigo(datos.codigo_pago, esperado):
        senales.append(
            _senal(
                Capa.IA,
                "CODIGO_DISTINTO",
                "El voucher paga otro código de pago o suministro, no el de esta deuda.",
                Riesgo.ALTO,
            )
        )


def _fecha(senales: list[Senal], pagado_el: date, hoy: date, esperada: CuotaEsperada) -> None:
    if pagado_el > hoy:
        senales.append(
            _senal(
                Capa.IA,
                "FECHA_FUTURA",
                "La fecha del pago es posterior a hoy. Revisa que sea el comprobante correcto.",
                Riesgo.ALTO,
            )
        )
    elif pagado_el < esperada.registrada_el:
        senales.append(
            _senal(
                Capa.IA,
                "FECHA_ANTERIOR_A_LA_DEUDA",
                "El pago es de antes de que se registrara la deuda: no puede ser su pago. Sube el "
                "comprobante del pago que hiciste para esta deuda.",
                Riesgo.ALTO,
            )
        )


def _contraste(
    senales: list[Senal], datos: DatosComprobante, lectura: Lectura, esperada: CuotaEsperada
) -> None:
    """Lo que no impide el pago, pero baja la confianza que ve el gerente."""
    if datos.importe is not None and datos.importe not in importes_en_texto(lectura.texto):
        senales.append(
            _senal(
                Capa.IA,
                "IMPORTE_NO_CONFIRMADO",
                "El importe que leímos no aparece tal cual en el texto del comprobante.",
                Riesgo.MEDIO,
            )
        )
    operacion = _alfanumerico(datos.numero_operacion or "")
    if not operacion:
        senales.append(
            _senal(
                Capa.IA,
                "SIN_OPERACION",
                "El comprobante no muestra un número de operación: no se puede rastrear el pago.",
                Riesgo.MEDIO,
            )
        )
    elif operacion not in _alfanumerico(lectura.texto):
        senales.append(
            _senal(
                Capa.IA,
                "OPERACION_NO_CONFIRMADA",
                "El número de operación que leímos no aparece en el texto del comprobante.",
                Riesgo.MEDIO,
            )
        )
    if datos.lugar and datos.lugar not in esperada.lugares:
        senales.append(
            _senal(
                Capa.IA,
                "LUGAR_NO_ACEPTADO",
                "Se pagó en un lugar que no se marcó para esta deuda.",
                Riesgo.MEDIO,
            )
        )
    if datos.empresa and esperada.empresa and not mismo_nombre(datos.empresa, esperada.empresa):
        senales.append(
            _senal(
                Capa.IA,
                "EMPRESA_DISTINTA",
                "La empresa a la que se pagó no parece la que emitió el documento de la deuda.",
                Riesgo.MEDIO,
            )
        )
    if datos.titular and esperada.titular and not mismo_nombre(datos.titular, esperada.titular):
        senales.append(
            _senal(
                Capa.IA,
                "TITULAR_DISTINTO",
                "El titular del voucher no coincide con el de la deuda.",
                Riesgo.MEDIO,
            )
        )
    if datos.comision:
        senales.append(
            _senal(
                Capa.IA,
                "CON_COMISION",
                f"El voucher cobra una comisión de {formatear_soles(datos.comision)} aparte del "
                "servicio.",
                Riesgo.BAJO,
            )
        )


def evaluar(
    datos: DatosComprobante, lectura: Lectura, esperada: CuotaEsperada, hoy: date
) -> list[Senal]:
    """Lo leído del comprobante frente a la cuota que dice pagar."""
    if not datos.es_comprobante:
        return [
            _senal(
                Capa.IA,
                "NO_ES_COMPROBANTE",
                "Este archivo no es el comprobante de un pago (parece el recibo o un documento "
                "por pagar). Sube el voucher o la captura de la operación.",
                Riesgo.ALTO,
            )
        ]
    if datos.moneda in (Moneda.DOLARES, Moneda.OTRA):
        return [
            _senal(
                Capa.IA,
                "OTRA_MONEDA",
                "El pago no está en soles. Deconsta registra solo pagos en soles (PEN).",
                Riesgo.ALTO,
            )
        ]
    senales: list[Senal] = []
    if datos.importe is None:
        senales.append(
            _senal(
                Capa.IA,
                "SIN_IMPORTE",
                "No pudimos leer cuánto se pagó. Sube una foto en la que se vea el importe.",
                Riesgo.ALTO,
            )
        )
    else:
        _importe(senales, datos, esperada)
    if datos.pagado_el is None:
        senales.append(
            _senal(
                Capa.IA,
                "SIN_FECHA",
                "No pudimos leer la fecha del pago. Sube una foto en la que se vea la fecha.",
                Riesgo.ALTO,
            )
        )
    else:
        _fecha(senales, datos.pagado_el, hoy, esperada)
    _codigo(senales, datos, lectura, esperada)
    _contraste(senales, datos, lectura, esperada)
    return senales


def senal_repetido() -> Senal:
    return _senal(
        Capa.LECTURA,
        "COMPROBANTE_REPETIDO",
        "Este comprobante ya respalda otro pago del espacio. Sube el de este pago.",
        Riesgo.ALTO,
    )


def estado_tras_analisis(analisis: AnalisisComprobante) -> EstadoComprobante:
    """Lo que no corresponde pesa más que lo ilegible: tapar el importe de una captura alterada
    no la convierte en una foto borrosa."""
    if cuenta_para_bloqueo(analisis.senales):
        return EstadoComprobante.RECHAZADO
    if {s.codigo for s in analisis.senales} & ILEGIBLES:
        return EstadoComprobante.ILEGIBLE
    if analisis.riesgo is Riesgo.ALTO:
        return EstadoComprobante.RECHAZADO
    return EstadoComprobante.LISTO


def cuenta_para_bloqueo(senales: Iterable[Senal]) -> bool:
    """Un comprobante rechazado porque no corresponde. Ni lo ilegible ni la posible mora
    cuentan."""
    return any(s.riesgo is Riesgo.ALTO and s.codigo not in NO_CUENTAN | ILEGIBLES for s in senales)
