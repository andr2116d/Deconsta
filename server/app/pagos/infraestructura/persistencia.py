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
from app.deudas.infraestructura.persistencia import PAGO_VIGENTE, RepositorioDeudasSql
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import Capa, Riesgo, Senal, TipoArchivo
from app.documentos.infraestructura.persistencia import (
    RepositorioCuentasSql,
    RepositorioDocumentosSql,
)
from app.notificaciones.infraestructura.persistencia import RepositorioNotificacionesSql
from app.pagos.dominio.errores import ComprobanteNoUsable, CuotaNoPagable, PedidoYaHecho
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    Comprobacion,
    Comprobante,
    DatosComprobante,
    EstadoComprobante,
    EstadoMora,
    Moneda,
    Mora,
    Pago,
    Pedido,
    Proposito,
    ResultadoComprobacion,
)

COLUMNAS_COMPROBANTE = """
    id, gerente_id, subido_por, deuda_id, cuota, tipo_archivo, tamano, paginas,
    nombre_archivo_cifrado, clave_objeto, huella_archivo, huella_operacion, estado,
    analisis_cifrado, subido_en, analizado_en, pago_id, proposito
"""
COLUMNAS_PAGO = """
    id, gerente_id, deuda_id, cuota, registrado_por, importe, comision, lugar_pago, pagado_el,
    estado, confianza, comprobaciones, registrado_en, mora
"""
COLUMNAS_MORA = """
    id, gerente_id, deuda_id, cuota, declarada_por, importe, prueba_id, nota, estado, confianza,
    comprobaciones, declarada_en, decidida_por, decidida_en, motivo_decision
"""
COMPROBANTE_USADO = {"uq_comprobante_pago_archivo_usado", "uq_comprobante_pago_operacion_usada"}
TEXTOS = ("medio", "empresa", "codigo_pago", "titular", "numero_operacion")
IMPORTES = ("importe", "comision", "total", "mora")


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
            # Los análisis anteriores a la mora no la traen.
            mora=_decimal(datos.get("mora")),
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
            proposito=Proposito(fila.proposito),
        )

    def agregar(self, comprobante: Comprobante) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO comprobante_pago (id, gerente_id, subido_por, deuda_id, cuota,"
                " tipo_archivo, tamano, paginas, nombre_archivo_cifrado, clave_objeto,"
                " huella_archivo, estado, subido_en, proposito) VALUES (:id, :gerente_id,"
                " :subido_por, :deuda_id, :cuota, :tipo_archivo, :tamano, :paginas, :nombre,"
                " :clave_objeto, :huella_archivo, :estado, :subido_en, :proposito)"
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
                "proposito": comprobante.proposito.value,
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

    def prueba_usada(self, gerente_id: UUID, huella: bytes) -> bool:
        fila = self._conexion.execute(
            text(
                "SELECT 1 FROM comprobante_pago c JOIN mora ON mora.prueba_id = c.id"
                " WHERE c.gerente_id = :gerente_id AND c.huella_archivo = :huella LIMIT 1"
            ),
            {"gerente_id": gerente_id, "huella": huella},
        ).first()
        return fila is not None

    def del_pago(self, pago_id: UUID) -> list[Comprobante]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_COMPROBANTE} FROM comprobante_pago WHERE pago_id = :pago_id"
                " ORDER BY subido_en"
            ),
            {"pago_id": pago_id},
        ).all()
        return [self._comprobante(fila) for fila in filas]

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
            " :comprobaciones, :registrado_en, :mora)"
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
                        "mora": pago.mora,
                    },
                )
        except IntegrityError as error:
            if _restriccion(error) == "uq_pago_cuota_vigente":
                raise CuotaNoPagable("CUOTA_YA_PAGADA") from error
            raise

    def _pagos(self, condicion: str, parametros: dict[str, Any], resto: str = "") -> list[Pago]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_PAGO}, decidido_por, decidido_en, motivo_decision,"
                " ARRAY(SELECT c.id FROM comprobante_pago c WHERE c.pago_id = pago.id"
                f" ORDER BY c.subido_en) AS comprobantes FROM pago WHERE {condicion}{resto}"
            ),
            parametros,
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
                comprobaciones=_comprobaciones_de(fila.comprobaciones),
                registrado_en=fila.registrado_en,
                comprobantes=tuple(fila.comprobantes),
                mora=fila.mora,
                decidido_por=fila.decidido_por,
                decidido_en=fila.decidido_en,
                motivo_decision=fila.motivo_decision,
            )
            for fila in filas
        ]

    def por_id(self, pago_id: UUID, *, bloquear: bool = False) -> Pago | None:
        cerrojo = " FOR UPDATE" if bloquear else ""
        pagos = self._pagos("id = :id", {"id": pago_id}, cerrojo)
        return pagos[0] if pagos else None

    def guardar(self, pago: Pago) -> None:
        self._conexion.execute(
            text(
                "UPDATE pago SET estado = :estado, decidido_por = :decidido_por,"
                " decidido_en = :decidido_en, motivo_decision = :motivo WHERE id = :id"
            ),
            {
                "id": pago.id,
                "estado": pago.estado.value,
                "decidido_por": pago.decidido_por,
                "decidido_en": pago.decidido_en,
                "motivo": pago.motivo_decision,
            },
        )

    def del_espacio(self, gerente_id: UUID, *, estado: EstadoPago | None = None) -> list[Pago]:
        filtro = " AND estado = :estado" if estado else ""
        return self._pagos(
            f"gerente_id = :gerente_id{filtro}",
            {"gerente_id": gerente_id, "estado": estado.value if estado else None},
            " ORDER BY registrado_en DESC LIMIT 200",
        )

    def devoluciones(self, gerente_id: UUID) -> dict[tuple[UUID, int], str]:
        filas = self._conexion.execute(
            text(
                "SELECT DISTINCT ON (p.deuda_id, p.cuota) p.deuda_id, p.cuota, p.motivo_decision"
                " FROM pago p WHERE p.gerente_id = :gerente_id AND p.estado = 'devuelto'"
                " AND NOT EXISTS (SELECT 1 FROM pago v WHERE v.deuda_id = p.deuda_id"
                " AND v.cuota = p.cuota AND v.estado IN ('por_verificar', 'confirmado'))"
                " ORDER BY p.deuda_id, p.cuota, p.decidido_en DESC"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return {(fila.deuda_id, fila.cuota): fila.motivo_decision for fila in filas}


def _comprobaciones_de(crudas: list[dict[str, str]]) -> tuple[Comprobacion, ...]:
    return tuple(
        Comprobacion(c["codigo"], c["titulo"], ResultadoComprobacion(c["resultado"]), c["detalle"])
        for c in crudas
    )


class RepositorioMorasSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    @staticmethod
    def _mora(fila: Row[Any]) -> Mora:
        return Mora(
            id=fila.id,
            gerente_id=fila.gerente_id,
            deuda_id=fila.deuda_id,
            cuota=fila.cuota,
            declarada_por=fila.declarada_por,
            importe=fila.importe,
            prueba_id=fila.prueba_id,
            nota=fila.nota,
            estado=EstadoMora(fila.estado),
            confianza=fila.confianza,
            comprobaciones=_comprobaciones_de(fila.comprobaciones),
            declarada_en=fila.declarada_en,
            decidida_por=fila.decidida_por,
            decidida_en=fila.decidida_en,
            motivo_decision=fila.motivo_decision,
        )

    def agregar(self, mora: Mora) -> None:
        sentencia = text(
            f"INSERT INTO mora ({COLUMNAS_MORA}) VALUES (:id, :gerente_id, :deuda_id, :cuota,"
            " :declarada_por, :importe, :prueba_id, :nota, :estado, :confianza, :comprobaciones,"
            " :declarada_en, NULL, NULL, NULL)"
        ).bindparams(bindparam("comprobaciones", type_=JSONB))
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(
                    sentencia,
                    {
                        "id": mora.id,
                        "gerente_id": mora.gerente_id,
                        "deuda_id": mora.deuda_id,
                        "cuota": mora.cuota,
                        "declarada_por": mora.declarada_por,
                        "importe": mora.importe,
                        "prueba_id": mora.prueba_id,
                        "nota": mora.nota,
                        "estado": mora.estado.value,
                        "confianza": mora.confianza,
                        "comprobaciones": _comprobaciones(mora.comprobaciones),
                        "declarada_en": mora.declarada_en,
                    },
                )
        except IntegrityError as error:
            restriccion = _restriccion(error)
            if restriccion == "uq_mora_cuota_vigente":
                raise CuotaNoPagable("MORA_YA_DECLARADA") from error
            if restriccion == "uq_mora_prueba_id":
                raise ComprobanteNoUsable("PRUEBA_YA_USADA") from error
            raise

    def _moras(self, condicion: str, parametros: dict[str, Any], resto: str = "") -> list[Mora]:
        filas = self._conexion.execute(
            text(f"SELECT {COLUMNAS_MORA} FROM mora WHERE {condicion}{resto}"), parametros
        ).all()
        return [self._mora(fila) for fila in filas]

    def por_id(self, mora_id: UUID, *, bloquear: bool = False) -> Mora | None:
        moras = self._moras("id = :id", {"id": mora_id}, " FOR UPDATE" if bloquear else "")
        return moras[0] if moras else None

    def guardar(self, mora: Mora) -> None:
        self._conexion.execute(
            text(
                "UPDATE mora SET estado = :estado, decidida_por = :decidida_por,"
                " decidida_en = :decidida_en, motivo_decision = :motivo WHERE id = :id"
            ),
            {
                "id": mora.id,
                "estado": mora.estado.value,
                "decidida_por": mora.decidida_por,
                "decidida_en": mora.decidida_en,
                "motivo": mora.motivo_decision,
            },
        )

    def del_espacio(self, gerente_id: UUID, *, estado: EstadoMora | None = None) -> list[Mora]:
        filtro = " AND estado = :estado" if estado else ""
        return self._moras(
            f"gerente_id = :gerente_id{filtro}",
            {"gerente_id": gerente_id, "estado": estado.value if estado else None},
            " ORDER BY declarada_en DESC LIMIT 200",
        )

    # La vigente gana a las rechazadas; entre rechazadas, la última.
    ORDEN_CUOTA = " ORDER BY deuda_id, cuota, estado = 'rechazada', declarada_en DESC"

    def de_la_cuota(self, deuda_id: UUID, cuota: int) -> Mora | None:
        moras = self._moras(
            "deuda_id = :deuda_id AND cuota = :cuota",
            {"deuda_id": deuda_id, "cuota": cuota},
            self.ORDEN_CUOTA + " LIMIT 1",
        )
        return moras[0] if moras else None

    def del_espacio_por_cuota(self, gerente_id: UUID) -> dict[tuple[UUID, int], Mora]:
        resultado: dict[tuple[UUID, int], Mora] = {}
        for mora in self._moras(
            "gerente_id = :gerente_id", {"gerente_id": gerente_id}, self.ORDEN_CUOTA
        ):
            resultado.setdefault((mora.deuda_id, mora.cuota), mora)
        return resultado


class RepositorioPedidosSql:
    COLUMNAS = (
        "id, gerente_id, deuda_id, cuota, asistente_id, nota, pedido_en, retirado_en, retirado_por"
    )

    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    @staticmethod
    def _pedido(fila: Row[Any]) -> Pedido:
        return Pedido(
            id=fila.id,
            gerente_id=fila.gerente_id,
            deuda_id=fila.deuda_id,
            cuota=fila.cuota,
            asistente_id=fila.asistente_id,
            nota=fila.nota,
            pedido_en=fila.pedido_en,
            retirado_en=fila.retirado_en,
            retirado_por=fila.retirado_por,
        )

    def agregar(self, pedido: Pedido) -> None:
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(
                    text(
                        f"INSERT INTO pedido_pago ({self.COLUMNAS}) VALUES (:id, :gerente_id,"
                        " :deuda_id, :cuota, :asistente_id, :nota, :pedido_en, NULL, NULL)"
                    ),
                    {
                        "id": pedido.id,
                        "gerente_id": pedido.gerente_id,
                        "deuda_id": pedido.deuda_id,
                        "cuota": pedido.cuota,
                        "asistente_id": pedido.asistente_id,
                        "nota": pedido.nota,
                        "pedido_en": pedido.pedido_en,
                    },
                )
        except IntegrityError as error:
            if _restriccion(error) == "uq_pedido_pago_vigente":
                raise PedidoYaHecho() from error
            raise

    def por_id(self, pedido_id: UUID, *, bloquear: bool = False) -> Pedido | None:
        cerrojo = " FOR UPDATE" if bloquear else ""
        fila = self._conexion.execute(
            text(f"SELECT {self.COLUMNAS} FROM pedido_pago WHERE id = :id{cerrojo}"),
            {"id": pedido_id},
        ).first()
        return self._pedido(fila) if fila else None

    def guardar(self, pedido: Pedido) -> None:
        self._conexion.execute(
            text(
                "UPDATE pedido_pago SET retirado_en = :retirado_en, retirado_por = :retirado_por"
                " WHERE id = :id"
            ),
            {
                "id": pedido.id,
                "retirado_en": pedido.retirado_en,
                "retirado_por": pedido.retirado_por,
            },
        )

    def pendientes(self, gerente_id: UUID, asistente_id: UUID | None = None) -> list[Pedido]:
        filtro = " AND p.asistente_id = :asistente_id" if asistente_id else ""
        columnas = ", ".join(f"p.{c.strip()}" for c in self.COLUMNAS.split(","))
        filas = self._conexion.execute(
            text(
                f"SELECT {columnas} FROM pedido_pago p JOIN deuda d ON d.id = p.deuda_id"
                f" WHERE p.gerente_id = :gerente_id AND p.retirado_en IS NULL{filtro}"
                " AND d.estado = 'registrada' AND NOT EXISTS (SELECT 1 FROM pago"
                " WHERE pago.deuda_id = p.deuda_id AND pago.cuota = p.cuota"
                f" AND {PAGO_VIGENTE}) ORDER BY p.pedido_en"
            ),
            {"gerente_id": gerente_id, "asistente_id": asistente_id},
        ).all()
        return [self._pedido(fila) for fila in filas]

    def asistente_activa(self, gerente_id: UUID, asistente_id: UUID) -> bool:
        fila = self._conexion.execute(
            text(
                "SELECT 1 FROM usuario WHERE id = :id AND rol = 'asistente'"
                " AND gerente_id = :gerente_id AND eliminada_en IS NULL AND bloqueada_en IS NULL"
            ),
            {"id": asistente_id, "gerente_id": gerente_id},
        ).first()
        return fila is not None


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
        self.moras = RepositorioMorasSql(self._conexion)
        self.pedidos = RepositorioPedidosSql(self._conexion)
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
