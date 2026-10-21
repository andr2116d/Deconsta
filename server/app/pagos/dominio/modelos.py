"""Pagos de las cuotas y los comprobantes que los respaldan.

Quien paga lo hace fuera del sistema (en un agente, por Yape, en la banca por internet…) y sube el
comprobante de esa cuota. Cada comprobante se analiza solo y se compara con la cuota: si no
corresponde, no respalda el pago. Un pago reúne uno o varios comprobantes de la misma cuota: un
agente puede cobrarla por partes el mismo día.

El pago de una asistente queda por verificar hasta que el gerente lo confirme; el del gerente queda
confirmado. La mora de una cuota vencida se declara con una prueba, que se sube y se analiza como un
comprobante; mientras el gerente no la aprueba o la rechaza, la cuota no se paga.

Lo que se comprobó se resume en una confianza de 0 a 95: nunca 100, porque una captura no se
confirma sin mirar la cuenta que recibió el dinero.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.deudas.dominio.modelos import EstadoPago, LugarPago
from app.documentos.dominio.modelos import Riesgo, Senal, TipoArchivo
from app.pagos.dominio.errores import PagoYaDecidido


class EstadoComprobante(StrEnum):
    ANALIZANDO = "analizando"
    LISTO = "listo"
    # No se pudo leer lo necesario (el importe, la fecha): se sube una foto más nítida.
    ILEGIBLE = "ilegible"
    # No corresponde a la cuota, muestra señales de alteración o no es un comprobante.
    RECHAZADO = "rechazado"
    # El mismo archivo o la misma operación ya respaldan otro pago.
    REPETIDO = "repetido"
    # El análisis no pudo completarse por un problema técnico.
    FALLIDO = "fallido"


class Proposito(StrEnum):
    """Para qué se subió el archivo: el voucher de un pago o la prueba de una mora."""

    PAGO = "pago"
    MORA = "mora"


class Moneda(StrEnum):
    SOLES = "PEN"
    DOLARES = "USD"
    OTRA = "otra"


@dataclass(frozen=True)
class DatosComprobante:
    """Lo que la revisión con IA leyó del comprobante. Cualquier campo puede faltar."""

    # Si es la constancia de un pago hecho y no, por ejemplo, el recibo que se va a pagar.
    es_comprobante: bool = True
    lugar: LugarPago | None = None
    # Con qué se pagó o quién cobró: «Yape», «Agente BCP», «Interbank App».
    medio: str | None = None
    # La empresa a la que se pagó.
    empresa: str | None = None
    codigo_pago: str | None = None
    titular: str | None = None
    numero_operacion: str | None = None
    pagado_el: date | None = None
    moneda: Moneda | None = None
    # Lo pagado por el servicio, sin la comisión.
    importe: Decimal | None = None
    comision: Decimal | None = None
    total: Decimal | None = None
    # En la prueba de una mora: la mora, si el documento la muestra aparte.
    mora: Decimal | None = None


@dataclass(frozen=True)
class AnalisisComprobante:
    datos: DatosComprobante | None
    senales: tuple[Senal, ...] = ()

    @property
    def riesgo(self) -> Riesgo:
        return max((s.riesgo for s in self.senales), key=lambda r: r.nivel, default=Riesgo.BAJO)


@dataclass
class Comprobante:
    id: UUID
    gerente_id: UUID
    subido_por: UUID
    deuda_id: UUID
    cuota: int
    tipo_archivo: TipoArchivo
    tamano: int
    paginas: int
    nombre_archivo: str
    clave_objeto: str
    huella_archivo: bytes
    estado: EstadoComprobante
    subido_en: datetime
    huella_operacion: bytes | None = None
    analisis: AnalisisComprobante | None = None
    analizado_en: datetime | None = None
    pago_id: UUID | None = None
    proposito: Proposito = Proposito.PAGO

    @property
    def datos(self) -> DatosComprobante | None:
        return self.analisis.datos if self.analisis else None


class ResultadoComprobacion(StrEnum):
    BIEN = "bien"
    # No se pudo comprobar: el dato no figura en el comprobante.
    SIN_DATO = "sin_dato"
    AVISO = "aviso"


@dataclass(frozen=True)
class Comprobacion:
    """Lo que se revisó del pago, para el gerente. Sin datos personales."""

    codigo: str
    titulo: str
    resultado: ResultadoComprobacion
    detalle: str


@dataclass
class Pago:
    id: UUID
    gerente_id: UUID
    deuda_id: UUID
    cuota: int
    registrado_por: UUID
    importe: Decimal
    comision: Decimal
    lugar: LugarPago | None
    pagado_el: date
    estado: EstadoPago
    confianza: int
    comprobaciones: tuple[Comprobacion, ...]
    registrado_en: datetime
    comprobantes: tuple[UUID, ...] = ()
    # Lo pagado por una mora aprobada, dentro del importe.
    mora: Decimal = Decimal("0")
    decidido_por: UUID | None = None
    decidido_en: datetime | None = None
    motivo_decision: str | None = None

    def _decidir(self, estado: EstadoPago, por: UUID, ahora: datetime, motivo: str | None) -> None:
        if self.estado is not EstadoPago.POR_VERIFICAR:
            raise PagoYaDecidido(
                "Este pago ya fue confirmado."
                if self.estado is EstadoPago.CONFIRMADO
                else "Este pago ya fue devuelto."
            )
        self.estado = estado
        self.decidido_por = por
        self.decidido_en = ahora
        self.motivo_decision = motivo

    def confirmar(self, por: UUID, ahora: datetime) -> None:
        self._decidir(EstadoPago.CONFIRMADO, por, ahora, None)

    def devolver(self, por: UUID, ahora: datetime, motivo: str) -> None:
        """La cuota vuelve a estar por pagar; los comprobantes no respaldan otro pago."""
        self._decidir(EstadoPago.DEVUELTO, por, ahora, motivo)


class EstadoMora(StrEnum):
    POR_APROBAR = "por_aprobar"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


@dataclass
class Mora:
    id: UUID
    gerente_id: UUID
    deuda_id: UUID
    cuota: int
    declarada_por: UUID
    importe: Decimal
    prueba_id: UUID
    nota: str | None
    estado: EstadoMora
    confianza: int
    comprobaciones: tuple[Comprobacion, ...]
    declarada_en: datetime
    decidida_por: UUID | None = None
    decidida_en: datetime | None = None
    motivo_decision: str | None = None

    def _decidir(self, estado: EstadoMora, por: UUID, ahora: datetime, motivo: str | None) -> None:
        if self.estado is not EstadoMora.POR_APROBAR:
            raise PagoYaDecidido(
                "Esta mora ya fue aprobada."
                if self.estado is EstadoMora.APROBADA
                else "Esta mora ya fue rechazada."
            )
        self.estado = estado
        self.decidida_por = por
        self.decidida_en = ahora
        self.motivo_decision = motivo

    def aprobar(self, por: UUID, ahora: datetime) -> None:
        """La cuota se puede pagar con la mora."""
        self._decidir(EstadoMora.APROBADA, por, ahora, None)

    def rechazar(self, por: UUID, ahora: datetime, motivo: str) -> None:
        """La cuota se paga sin la mora; quien la declaró puede volver a declararla."""
        self._decidir(EstadoMora.RECHAZADA, por, ahora, motivo)
