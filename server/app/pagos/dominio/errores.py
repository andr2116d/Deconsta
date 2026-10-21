"""Errores de los pagos. Cada uno trae un código estable para el frontend y un mensaje que dice qué
ocurrió y qué hacer."""

from collections.abc import Mapping
from datetime import datetime


class ErrorPagos(Exception):
    codigo = "ERROR_PAGOS"
    mensaje = "No pudimos completar la operación con el pago."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class CamposFaltantes(ErrorPagos):
    codigo = "CAMPOS_OBLIGATORIOS"
    mensaje = "Faltan datos obligatorios."


class PagoInvalido(ErrorPagos):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los datos marcados."


class ComprobanteNoEncontrado(ErrorPagos):
    codigo = "COMPROBANTE_NO_ENCONTRADO"
    mensaje = "No encontramos ese comprobante en tu espacio."


class CuotaNoPagable(ErrorPagos):
    """La cuota no se puede pagar ahora. El código dice por qué."""

    MENSAJES = {
        "DEUDA_POR_AUTORIZAR": (
            "Esta deuda espera la autorización del gerente: no se paga hasta que la autorice."
        ),
        "DEUDA_NO_SE_PAGA": "Esta deuda fue rechazada o anulada: ya no se paga.",
        "CUOTA_YA_PAGADA": (
            "Esta cuota ya tiene un pago registrado. Si falta otra cuota, elige esa."
        ),
        "MORA_POR_APROBAR": (
            "La mora de esta cuota espera la aprobación del gerente: no se paga hasta que la "
            "apruebe o la rechace."
        ),
        "CUOTA_NO_VENCIDA": "Esta cuota aún no vence: no puede tener mora.",
        "MORA_YA_DECLARADA": (
            "Esta cuota ya tiene una mora declarada. Espera la decisión del gerente."
        ),
    }

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        super().__init__(self.MENSAJES[codigo])


class ComprobanteNoUsable(ErrorPagos):
    """El comprobante no puede respaldar el pago. El código dice por qué."""

    MENSAJES = {
        "COMPROBANTE_EN_ANALISIS": (
            "Todavía estamos revisando el comprobante. Espera unos segundos."
        ),
        "COMPROBANTE_ILEGIBLE": (
            "No pudimos leer el comprobante. Sube una foto nítida y completa, o la captura "
            "original de la operación."
        ),
        "COMPROBANTE_RECHAZADO": (
            "El comprobante no corresponde a esta cuota. Revisa lo que encontramos y sube el "
            "correcto."
        ),
        "COMPROBANTE_REPETIDO": "Este comprobante ya respalda otro pago. Sube el de este pago.",
        "COMPROBANTE_FALLIDO": (
            "No pudimos leer el comprobante solo. Escribe sus datos a mano o súbelo otra vez."
        ),
        "COMPROBANTE_NO_SE_COMPLETA": (
            "Solo se escriben a mano los datos de un voucher que no se pudo leer solo."
        ),
        "COMPROBANTE_YA_USADO": "Este comprobante ya respalda otro pago. Sube el de este pago.",
        "COMPROBANTE_DE_OTRA_CUOTA": (
            "Ese comprobante se subió para otra cuota. Súbelo otra vez desde esta cuota."
        ),
        "COMPROBANTE_DE_MORA": (
            "Ese archivo se subió como prueba de la mora. Para el pago, súbelo como voucher."
        ),
        "COMPROBANTE_DE_PAGO": (
            "Ese archivo se subió como voucher del pago. Para la mora, súbelo como prueba."
        ),
        "PRUEBA_YA_USADA": "Esa prueba ya respalda otra mora. Sube la de esta cuota.",
    }

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        mensaje = self.MENSAJES[codigo]
        super().__init__(mensaje, campos={"comprobantes": mensaje})


class ComprobantesNoCombinan(ErrorPagos):
    codigo = "COMPROBANTES_NO_COMBINAN"
    mensaje = (
        "Solo un pago en agente se registra con varios vouchers, y todos deben ser del mismo día "
        "y de operaciones distintas. Si no, registra un voucher por pago."
    )

    def __init__(self) -> None:
        super().__init__(campos={"comprobantes": self.mensaje})


class ImporteNoCoincide(ErrorPagos):
    codigo = "IMPORTE_NO_COINCIDE"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, campos={"comprobantes": mensaje})


class RegistroPagosBloqueado(ErrorPagos):
    codigo = "REGISTRO_PAGOS_BLOQUEADO"
    mensaje = (
        "Tu registro de pagos está en pausa porque varios comprobantes no correspondían a sus "
        "cuotas. Tu gerente puede permitirte registrar pagos otra vez."
    )

    def __init__(self, desde: datetime) -> None:
        self.desde = desde
        super().__init__()


class PagoNoEncontrado(ErrorPagos):
    codigo = "PAGO_NO_ENCONTRADO"
    mensaje = "No encontramos ese pago en tu espacio."


class MoraNoEncontrada(ErrorPagos):
    codigo = "MORA_NO_ENCONTRADA"
    mensaje = "No encontramos esa mora en tu espacio."


class PedidoNoEncontrado(ErrorPagos):
    codigo = "PEDIDO_NO_ENCONTRADO"
    mensaje = "No encontramos ese pedido en tu espacio."


class PedidoYaHecho(ErrorPagos):
    codigo = "PEDIDO_YA_HECHO"
    mensaje = (
        "Ya pediste que paguen esta cuota. Retira ese pedido si quieres pedírselo a otra asistente."
    )


class PagoYaDecidido(ErrorPagos):
    codigo = "ESTADO_NO_PERMITE"


class BloqueoPagosNoEncontrado(ErrorPagos):
    codigo = "BLOQUEO_NO_ENCONTRADO"
    mensaje = "Esa asistente puede registrar pagos: no tiene un bloqueo vigente."
