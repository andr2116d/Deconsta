"""Adaptadores de Postgres para los pagos, sus comprobantes y el bloqueo del registro de pagos.

El nombre del archivo y el análisis del comprobante (titular, código de pago, número de operación)
se guardan cifrados con AES-256-GCM, con el id del comprobante como contexto. Las huellas son
HMAC. Vincular un comprobante choca con los índices únicos del espacio si su archivo o su operación
ya respaldan otro pago, y registrar el pago choca si la cuota ya tiene uno vigente: la base es la
última barrera contra duplicados.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.persistencia import RegistroAuditoriaSql
from app.deudas.dominio.modelos import EstadoPago, LugarPago
from app.deudas.infraestructura.persistencia import RepositorioDeudasSql
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import Capa, Riesgo, Senal, TipoArchivo
from app.documentos.infraestructura.persistencia import (
    RepositorioCuentasSql,
    RepositorioDocumentosSql,
)
from app.notificaciones.infraestructura.persistencia import RepositorioNotificacionesSql
from app.pagos.dominio.errores import ComprobanteNoUsable, CuotaNoPagable
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    Comprobacion,
    Comprobante,
    DatosComprobante,
    EstadoComprobante,
    Moneda,
    Pago,
    ResultadoComprobacion,
)

COLUMNAS_COMPROBANTE = """
    id, gerente_id, subido_por, deuda_id, cuota, tipo_archivo, tamano, paginas,
    nombre_archivo_cifrado, clave_objeto, huella_archivo, huella_operacion, estado,
    analisis_cifrado, subido_en, analizado_en, pago_id
"""
COLUMNAS_PAGO = """
    id, gerente_id, deuda_id, cuota, registrado_por, importe, comision, lugar_pago, pagado_el,
    estado, confianza, comprobaciones, registrado_en
"""
COMPROBANTE_USADO = {"uq_comprobante_pago_archivo_usado", "uq_comprobante_pago_operacion_usada"}
TEXTOS = ("medio", "empresa", "codigo_pago", "titular", "numero_operacion")
IMPORTES = ("importe", "comision", "total")


def contexto(campo: str, comprobante_id: UUID) -> str:
    return f"comprobante_pago.{campo}:{comprobante_id}"


def _restriccion(error: IntegrityError) -> str | None:
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)


def analisis_a_json(analisis: AnalisisComprobante) -> str:
    datos = analisis.datos
    return json.dumps(
        {
            "senales": [
                {"capa": s.capa, "codigo": s.codigo, "detalle": s.detalle, "riesgo": s.riesgo}
                for s in analisis.senales
            ],
            "datos": None
            if datos is None
            else {
                **{campo: getattr(datos, campo) for campo in TEXTOS},
                **{
                    campo: str(valor) if (valor := getattr(datos, campo)) is not None else None
                    for campo in IMPORTES
                },
                "es_comprobante": datos.es_comprobante,
                "lugar": datos.lugar.value if datos.lugar else None,
                "pagado_el": datos.pagado_el.isoformat() if datos.pagado_el else None,
                "moneda": datos.moneda.value if datos.moneda else None,
            },
        },
        ensure_ascii=False,
    )


def _decimal(valor: str | None) -> Decimal | None:
    return Decimal(valor) if valor else None


def analisis_de_json(texto: str) -> AnalisisComprobante:
    crudo = json.loads(texto)
    senales = tuple(
        Senal(Capa(s["capa"]), s["codigo"], s["detalle"], Riesgo(s["riesgo"]))
        for s in crudo["senales"]
    )
    datos = crudo["datos"]
    if datos is None:
        return AnalisisComprobante(None, senales)
    return AnalisisComprobante(
        DatosComprobante(
            es_comprobante=datos["es_comprobante"],
            lugar=LugarPago(datos["lugar"]) if datos["lugar"] else None,
            pagado_el=date.fromisoformat(datos["pagado_el"]) if datos["pagado_el"] else None,
            moneda=Moneda(datos["moneda"]) if datos["moneda"] else None,
            medio=datos["medio"],
            empresa=datos["empresa"],
            codigo_pago=datos["codigo_pago"],
            titular=datos["titular"],
            numero_operacion=datos["numero_operacion"],
            importe=_decimal(datos["importe"]),
            comision=_decimal(datos["comision"]),
            total=_decimal(datos["total"]),
        ),
        senales,
    )


class RepositorioComprobantesSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador

    def _comprobante(self, fila: Row[Any]) -> Comprobante:
        return Comprobante(
            id=fila.id,
            gerente_id=fila.gerente_id,
            subido_por=fila.subido_por,
            deuda_id=fila.deuda_id,
            cuota=fila.cuota,
            tipo_archivo=TipoArchivo(fila.tipo_archivo),
            tamano=fila.tamano,
            paginas=fila.paginas,
            nombre_archivo=self._cifrador.descifrar(
                fila.nombre_archivo_cifrado, contexto("nombre_archivo", fila.id)
            ),
            clave_objeto=fila.clave_objeto,
            huella_archivo=bytes(fila.huella_archivo),
            estado=EstadoComprobante(fila.estado),
            subido_en=fila.subido_en,
            huella_operacion=bytes(fila.huella_operacion) if fila.huella_operacion else None,
            analisis=analisis_de_json(
                self._cifrador.descifrar(fila.analisis_cifrado, contexto("analisis", fila.id))
            )
            if fila.analisis_cifrado
            else None,
            analizado_en=fila.analizado_en,
            pago_id=fila.pago_id,
        )

    def agregar(self, comprobante: Comprobante) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO comprobante_pago (id, gerente_id, subido_por, deuda_id, cuota,"
                " tipo_archivo, tamano, paginas, nombre_archivo_cifrado, clave_objeto,"
                " huella_archivo, estado, subido_en) VALUES (:id, :gerente_id, :subido_por,"
                " :deuda_id, :cuota, :tipo_archivo, :tamano, :paginas, :nombre, :clave_objeto,"
                " :huella_archivo, :estado, :subido_en)"
            ),
            {
                "id": comprobante.id,
                "gerente_id": comprobante.gerente_id,
                "subido_por": comprobante.subido_por,
                "deuda_id": comprobante.deuda_id,
                "cuota": comprobante.cuota,
                "tipo_archivo": comprobante.tipo_archivo.value,
                "tamano": comprobante.tamano,
                "paginas": comprobante.paginas,
                "nombre": self._cifrador.cifrar(
                    comprobante.nombre_archivo, contexto("nombre_archivo", comprobante.id)
                ),
                "clave_objeto": comprobante.clave_objeto,
                "huella_archivo": comprobante.huella_archivo,
                "estado": comprobante.estado.value,
                "subido_en": comprobante.subido_en,
            },
        )

    def por_id(self, comprobante_id: UUID, *, bloquear: bool = False) -> Comprobante | None:
        cerrojo = " FOR UPDATE" if bloquear else ""
        fila = self._conexion.execute(
            text(f"SELECT {COLUMNAS_COMPROBANTE} FROM comprobante_pago WHERE id = :id{cerrojo}"),
            {"id": comprobante_id},
        ).first()
        return self._comprobante(fila) if fila else None

    def guardar(self, comprobante: Comprobante) -> None:
        analisis = comprobante.analisis
        self._conexion.execute(
            text(
                "UPDATE comprobante_pago SET estado = :estado, riesgo = :riesgo,"
                " analisis_cifrado = :analisis, huella_operacion = :huella_operacion,"
                " analizado_en = :analizado_en WHERE id = :id"
            ),
            {
                "id": comprobante.id,
                "estado": comprobante.estado.value,
                "riesgo": analisis.riesgo.value if analisis else None,
                "analisis": self._cifrador.cifrar(
                    analisis_a_json(analisis), contexto("analisis", comprobante.id)
                )
                if analisis
                else None,
                "huella_operacion": comprobante.huella_operacion,
                "analizado_en": comprobante.analizado_en,
            },
        )

    def _usado(self, columna: str, gerente_id: UUID, huella: bytes) -> bool:
        fila = self._conexion.execute(
            text(
                "SELECT 1 FROM comprobante_pago WHERE gerente_id = :gerente_id"
                f" AND {columna} = :huella AND pago_id IS NOT NULL LIMIT 1"
            ),
            {"gerente_id": gerente_id, "huella": huella},
        ).first()
        return fila is not None

    def archivo_usado(self, gerente_id: UUID, huella: bytes) -> bool:
        return self._usado("huella_archivo", gerente_id, huella)

    def operacion_usada(self, gerente_id: UUID, huella: bytes) -> bool:
        return self._usado("huella_operacion", gerente_id, huella)

    def vincular(self, comprobantes: list[UUID], pago_id: UUID) -> None:
        sentencia = text(
            "UPDATE comprobante_pago SET pago_id = :pago_id WHERE id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        try:
            # Un savepoint: si choca con la unicidad, la transacción sigue utilizable.
            with self._conexion.begin_nested():
                self._conexion.execute(sentencia, {"pago_id": pago_id, "ids": comprobantes})
        except IntegrityError as error:
            if _restriccion(error) in COMPROBANTE_USADO:
                raise ComprobanteNoUsable("COMPROBANTE_YA_USADO") from error
            raise


def _comprobaciones(lista: tuple[Comprobacion, ...]) -> list[dict[str, str]]:
    return [
        {"codigo": c.codigo, "titulo": c.titulo, "resultado": c.resultado, "detalle": c.detalle}
        for c in lista
    ]


class RepositorioPagosSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def agregar(self, pago: Pago) -> None:
        sentencia = text(
            f"INSERT INTO pago ({COLUMNAS_PAGO}) VALUES (:id, :gerente_id, :deuda_id, :cuota,"
            " :registrado_por, :importe, :comision, :lugar_pago, :pagado_el, :estado, :confianza,"
            " :comprobaciones, :registrado_en)"
        ).bindparams(bindparam("comprobaciones", type_=JSONB))
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(
                    sentencia,
                    {
                        "id": pago.id,
                        "gerente_id": pago.gerente_id,
                        "deuda_id": pago.deuda_id,
                        "cuota": pago.cuota,
                        "registrado_por": pago.registrado_por,
                        "importe": pago.importe,
                        "comision": pago.comision,
                        "lugar_pago": pago.lugar.value if pago.lugar else None,
                        "pagado_el": pago.pagado_el,
                        "estado": pago.estado.value,
                        "confianza": pago.confianza,
                        "comprobaciones": _comprobaciones(pago.comprobaciones),
                        "registrado_en": pago.registrado_en,
                    },
                )
        except IntegrityError as error:
            if _restriccion(error) == "uq_pago_cuota_vigente":
                raise CuotaNoPagable("CUOTA_YA_PAGADA") from error
            raise

    def del_espacio(self, gerente_id: UUID) -> list[Pago]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_PAGO}, ARRAY(SELECT c.id FROM comprobante_pago c"
                " WHERE c.pago_id = pago.id ORDER BY c.subido_en) AS comprobantes"
                " FROM pago WHERE gerente_id = :gerente_id ORDER BY registrado_en DESC LIMIT 200"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [
            Pago(
                id=fila.id,
                gerente_id=fila.gerente_id,
                deuda_id=fila.deuda_id,
                cuota=fila.cuota,
                registrado_por=fila.registrado_por,
                importe=fila.importe,
                comision=fila.comision,
                lugar=LugarPago(fila.lugar_pago) if fila.lugar_pago else None,
                pagado_el=fila.pagado_el,
                estado=EstadoPago(fila.estado),
                confianza=fila.confianza,
                comprobaciones=tuple(
                    Comprobacion(
                        c["codigo"],
                        c["titulo"],
                        ResultadoComprobacion(c["resultado"]),
                        c["detalle"],
                    )
                    for c in fila.comprobaciones
                ),
                registrado_en=fila.registrado_en,
                comprobantes=tuple(fila.comprobantes),
            )
            for fila in filas
        ]


class RepositorioBloqueosPagosSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    @staticmethod
    def _bloqueo(fila: Row[Any]) -> Bloqueo:
        return Bloqueo(fila.id, fila.asistente_id, fila.gerente_id, fila.bloqueado_en)

    def vigente(self, asistente_id: UUID) -> Bloqueo | None:
        fila = self._conexion.execute(
            text(
                "SELECT id, asistente_id, gerente_id, bloqueado_en FROM bloqueo_registro_pago"
                " WHERE asistente_id = :asistente_id AND levantado_en IS NULL"
            ),
            {"asistente_id": asistente_id},
        ).first()
        return self._bloqueo(fila) if fila else None

    def vigentes_del_espacio(self, gerente_id: UUID) -> list[Bloqueo]:
        filas = self._conexion.execute(
            text(
                "SELECT id, asistente_id, gerente_id, bloqueado_en FROM bloqueo_registro_pago"
                " WHERE gerente_id = :gerente_id AND levantado_en IS NULL ORDER BY bloqueado_en"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [self._bloqueo(fila) for fila in filas]

    def registrar_intento(self, asistente_id: UUID, comprobante_id: UUID, ahora: datetime) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO intento_comprobante_rechazado (asistente_id, comprobante_id,"
                " ocurrido_en) VALUES (:asistente_id, :comprobante_id, :ahora)"
            ),
            {"asistente_id": asistente_id, "comprobante_id": comprobante_id, "ahora": ahora},
        )

    def contar_intentos(self, asistente_id: UUID, desde: datetime) -> int:
        return int(
            self._conexion.execute(
                text(
                    "SELECT count(*) FROM intento_comprobante_rechazado"
                    " WHERE asistente_id = :asistente_id AND ocurrido_en > :desde"
                ),
                {"asistente_id": asistente_id, "desde": desde},
            ).scalar_one()
        )

    def ultimo_levantamiento(self, asistente_id: UUID) -> datetime | None:
        valor: datetime | None = self._conexion.execute(
            text(
                "SELECT max(levantado_en) FROM bloqueo_registro_pago"
                " WHERE asistente_id = :asistente_id"
            ),
            {"asistente_id": asistente_id},
        ).scalar_one()
        return valor

    def bloquear(self, bloqueo: Bloqueo) -> bool:
        fila = self._conexion.execute(
            text(
                "INSERT INTO bloqueo_registro_pago (id, asistente_id, gerente_id, bloqueado_en)"
                " VALUES (:id, :asistente_id, :gerente_id, :bloqueado_en)"
                " ON CONFLICT (asistente_id) WHERE levantado_en IS NULL DO NOTHING RETURNING id"
            ),
            {
                "id": bloqueo.id,
                "asistente_id": bloqueo.asistente_id,
                "gerente_id": bloqueo.gerente_id,
                "bloqueado_en": bloqueo.bloqueado_en,
            },
        ).first()
        return fila is not None

    def levantar(self, bloqueo_id: UUID, levantado_por: UUID, ahora: datetime) -> None:
        self._conexion.execute(
            text(
                "UPDATE bloqueo_registro_pago SET levantado_en = :ahora,"
                " levantado_por = :levantado_por WHERE id = :id"
            ),
            {"id": bloqueo_id, "levantado_por": levantado_por, "ahora": ahora},
        )


class UnidadPagosSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.comprobantes = RepositorioComprobantesSql(self._conexion, self._cifrador)
        self.pagos = RepositorioPagosSql(self._conexion)
        self.deudas = RepositorioDeudasSql(self._conexion, self._cifrador)
        self.documentos = RepositorioDocumentosSql(self._conexion, self._cifrador)
        self.bloqueos = RepositorioBloqueosPagosSql(self._conexion)
        self.cuentas = RepositorioCuentasSql(self._conexion, self._cifrador)
        self.notificaciones = RepositorioNotificacionesSql(self._conexion)
        self.auditoria = RegistroAuditoriaSql(self._conexion)
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            if tipo is None:
                self._transaccion.commit()
            else:
                self._transaccion.rollback()
        finally:
            self._conexion.close()
