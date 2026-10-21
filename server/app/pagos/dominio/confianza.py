"""Cuánto respaldan los comprobantes que el pago es verdadero, para el gerente.

Cada comprobación pesa según lo que prueba: el importe, el código de pago y la ausencia de señales
de alteración pesan más que el titular o el lugar. Bien vale completo; sin dato, la mitad; con
aviso, nada. El resultado se escala a 95 como máximo: una captura no se confirma del todo sin
mirar la cuenta que recibió el dinero.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.documentos.dominio.modelos import Senal
from app.pagos.dominio.modelos import Comprobacion, DatosComprobante, ResultadoComprobacion
from app.pagos.dominio.reglas import CuotaEsperada

CONFIANZA_MAXIMA = 95
VALORES = {
    ResultadoComprobacion.BIEN: 1.0,
    ResultadoComprobacion.SIN_DATO: 0.5,
    ResultadoComprobacion.AVISO: 0.0,
}
GRAVEDAD = [ResultadoComprobacion.BIEN, ResultadoComprobacion.SIN_DATO, ResultadoComprobacion.AVISO]


@dataclass(frozen=True)
class Criterio:
    codigo: str
    titulo: str
    peso: int
    bien: str
    avisos: frozenset[str] = frozenset()
    sin_dato: frozenset[str] = frozenset()


CRITERIOS = (
    Criterio(
        "importe",
        "Importe",
        3,
        "Lo pagado coincide con la cuota.",
        avisos=frozenset({"IMPORTE_NO_CONFIRMADO"}),
    ),
    Criterio(
        "codigo_pago",
        "Código de pago",
        3,
        "El comprobante paga el código o suministro de esta deuda.",
        sin_dato=frozenset({"SIN_CODIGO"}),
    ),
    Criterio(
        "autenticidad",
        "Señales de alteración",
        3,
        "La revisión no encontró señales de alteración.",
        avisos=frozenset({"AUTENTICIDAD_DUDOSA"}),
    ),
    Criterio(
        "archivo",
        "Archivo",
        2,
        "No pasó por programas de edición.",
        avisos=frozenset(
            {
                "EDITADO_DESPUES",
                "CREADO_EN_PROCESADOR",
                "PDF_MODIFICADO",
                "CONTENIDO_ACTIVO",
                "FECHA_MODIFICACION_POSTERIOR",
            }
        ),
    ),
    Criterio(
        "operacion",
        "Número de operación",
        2,
        "Tiene número de operación y no respalda otro pago.",
        avisos=frozenset({"OPERACION_NO_CONFIRMADA"}),
        sin_dato=frozenset({"SIN_OPERACION"}),
    ),
    Criterio(
        "empresa",
        "Empresa",
        2,
        "Se pagó a la empresa de la deuda.",
        avisos=frozenset({"EMPRESA_DISTINTA"}),
    ),
    Criterio(
        "lugar",
        "Lugar de pago",
        1,
        "Se pagó en un lugar que acepta la deuda.",
        avisos=frozenset({"LUGAR_NO_ACEPTADO"}),
    ),
    Criterio(
        "titular",
        "Titular",
        1,
        "El titular coincide con el de la deuda.",
        avisos=frozenset({"TITULAR_DISTINTO"}),
    ),
    Criterio(
        "fecha",
        "Fecha del pago",
        1,
        "No es futura ni anterior al registro de la deuda.",
    ),
)

SIN_DATO = {
    "codigo_pago": "Ni el comprobante ni la deuda permiten comparar el código de pago.",
    "empresa": "No se pudo comparar la empresa: falta en el comprobante o en la deuda.",
    "lugar": "El comprobante no deja claro dónde se pagó.",
    "titular": "No se pudo comparar el titular: falta en el comprobante o en la deuda.",
}


def _faltante(criterio: str, datos: DatosComprobante, esperada: CuotaEsperada) -> bool:
    """Lo que no se pudo comparar porque el dato no figura."""
    return {
        "codigo_pago": not esperada.codigo_pago,
        "empresa": not (datos.empresa and esperada.empresa),
        "lugar": datos.lugar is None,
        "titular": not (datos.titular and esperada.titular),
    }.get(criterio, False)


def _resultado(
    criterio: Criterio, senales: Sequence[Senal], datos: DatosComprobante, esperada: CuotaEsperada
) -> tuple[ResultadoComprobacion, str]:
    for senal in senales:
        if senal.codigo in criterio.avisos:
            return ResultadoComprobacion.AVISO, senal.detalle
    for senal in senales:
        if senal.codigo in criterio.sin_dato:
            return ResultadoComprobacion.SIN_DATO, senal.detalle
    if _faltante(criterio.codigo, datos, esperada):
        return ResultadoComprobacion.SIN_DATO, SIN_DATO[criterio.codigo]
    return ResultadoComprobacion.BIEN, criterio.bien


def comprobaciones(
    comprobantes: Sequence[tuple[DatosComprobante, Sequence[Senal]]], esperada: CuotaEsperada
) -> tuple[Comprobacion, ...]:
    """Una comprobación por criterio: con varios comprobantes, vale el peor resultado."""
    resultado = []
    for criterio in CRITERIOS:
        peor = (ResultadoComprobacion.BIEN, criterio.bien)
        for datos, senales in comprobantes:
            actual = _resultado(criterio, senales, datos, esperada)
            if GRAVEDAD.index(actual[0]) > GRAVEDAD.index(peor[0]):
                peor = actual
        resultado.append(Comprobacion(criterio.codigo, criterio.titulo, *peor))
    return tuple(resultado)


def confianza(lista: Sequence[Comprobacion]) -> int:
    pesos = {c.codigo: c.peso for c in CRITERIOS}
    total = sum(pesos[c.codigo] for c in lista)
    if not total:
        return 0
    obtenido = sum(pesos[c.codigo] * VALORES[c.resultado] for c in lista)
    return round(CONFIANZA_MAXIMA * obtenido / total)
