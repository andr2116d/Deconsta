"""Adaptadores de Postgres para los documentos y los bloqueos del registro de deudas.

El nombre del archivo y el análisis (lo leído del documento: titular, código de pago…) se guardan
cifrados con AES-256-GCM, con el id del documento como contexto. Las huellas son HMAC.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.modelos import Rol
from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.persistencia import RegistroAuditoriaSql, RepositorioUsuariosSql
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import (
    Analisis,
    Capa,
    CuotaLeida,
    DatosLeidos,
    DeudaDelDocumento,
    Documento,
    EstadoDocumento,
    Riesgo,
    Senal,
    TipoArchivo,
    TipoDocumento,
)
from app.documentos.dominio.puertos import CategoriaConocida
from app.notificaciones.infraestructura.persistencia import RepositorioNotificacionesSql

COLUMNAS = """
    id, gerente_id, subido_por, tipo_archivo, tamano, paginas, nombre_archivo_cifrado,
    clave_objeto, huella_archivo, clave_negocio_huella, huellas_texto, estado, tipo_documento,
    analisis_cifrado, repetido_de, subido_en, analizado_en, deuda_id
"""


def contexto(campo: str, documento_id: UUID) -> str:
    return f"documento_deuda.{campo}:{documento_id}"


def analisis_a_json(analisis: Analisis) -> str:
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
                **{
                    campo: getattr(datos, campo)
                    for campo in (
                        "emisor",
                        "emisor_ruc",
                        "concepto",
                        "titular_nombre",
                        "titular_tipo_documento",
                        "titular_numero_documento",
                        "codigo_pago",
                        "numero_documento",
                        "periodo",
                        "categoria",
                        "categoria_nueva",
                        "lugar_pago",
                    )  # fmt: skip
                },
                "tipo": datos.tipo.value,
                "importe": str(datos.importe) if datos.importe is not None else None,
                "vence_el": datos.vence_el.isoformat() if datos.vence_el else None,
                "cuotas": [
                    {
                        "numero": c.numero,
                        "vence_el": c.vence_el.isoformat(),
                        "importe": str(c.importe),
                    }
                    for c in datos.cuotas
                ],
            },
        },
        ensure_ascii=False,
    )


def analisis_de_json(texto: str) -> Analisis:
    crudo = json.loads(texto)
    senales = tuple(
        Senal(Capa(s["capa"]), s["codigo"], s["detalle"], Riesgo(s["riesgo"]))
        for s in crudo["senales"]
    )
    datos = crudo["datos"]
    if datos is None:
        return Analisis(None, senales)
    return Analisis(
        DatosLeidos(
            **{
                clave: valor
                for clave, valor in datos.items()
                if clave not in ("tipo", "importe", "vence_el", "cuotas")
            },
            tipo=TipoDocumento(datos["tipo"]),
            importe=Decimal(datos["importe"]) if datos["importe"] else None,
            vence_el=date.fromisoformat(datos["vence_el"]) if datos["vence_el"] else None,
            cuotas=tuple(
                CuotaLeida(c["numero"], date.fromisoformat(c["vence_el"]), Decimal(c["importe"]))
                for c in datos["cuotas"]
            ),
        ),
        senales,
    )


class RepositorioDocumentosSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador

    def _documento(self, fila: Row[Any]) -> Documento:
        analisis = (
            analisis_de_json(
                self._cifrador.descifrar(fila.analisis_cifrado, contexto("analisis", fila.id))
            )
            if fila.analisis_cifrado
            else None
        )
        return Documento(
            id=fila.id,
            gerente_id=fila.gerente_id,
            subido_por=fila.subido_por,
            tipo_archivo=TipoArchivo(fila.tipo_archivo),
            tamano=fila.tamano,
            paginas=fila.paginas,
            nombre_archivo=self._cifrador.descifrar(
                fila.nombre_archivo_cifrado, contexto("nombre_archivo", fila.id)
            ),
            clave_objeto=fila.clave_objeto,
            huella_archivo=bytes(fila.huella_archivo),
            estado=EstadoDocumento(fila.estado),
            subido_en=fila.subido_en,
            clave_negocio_huella=bytes(fila.clave_negocio_huella)
            if fila.clave_negocio_huella
            else None,
            huellas_texto=tuple(bytes(h) for h in fila.huellas_texto),
            analisis=analisis,
            analizado_en=fila.analizado_en,
            repetido_de=fila.repetido_de,
            deuda_id=fila.deuda_id,
            tipo_documento=TipoDocumento(fila.tipo_documento) if fila.tipo_documento else None,
        )

    def agregar(self, documento: Documento) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO documento_deuda (id, gerente_id, subido_por, tipo_archivo, tamano,"
                " paginas, nombre_archivo_cifrado, clave_objeto, huella_archivo, estado, subido_en)"
                " VALUES (:id, :gerente_id, :subido_por, :tipo_archivo, :tamano, :paginas,"
                " :nombre, :clave_objeto, :huella_archivo, :estado, :subido_en)"
            ),
            {
                "id": documento.id,
                "gerente_id": documento.gerente_id,
                "subido_por": documento.subido_por,
                "tipo_archivo": documento.tipo_archivo.value,
                "tamano": documento.tamano,
                "paginas": documento.paginas,
                "nombre": self._cifrador.cifrar(
                    documento.nombre_archivo, contexto("nombre_archivo", documento.id)
                ),
                "clave_objeto": documento.clave_objeto,
                "huella_archivo": documento.huella_archivo,
                "estado": documento.estado.value,
                "subido_en": documento.subido_en,
            },
        )

    def por_id(self, documento_id: UUID, *, bloquear: bool = False) -> Documento | None:
        cerrojo = " FOR UPDATE" if bloquear else ""
        fila = self._conexion.execute(
            text(f"SELECT {COLUMNAS} FROM documento_deuda WHERE id = :id{cerrojo}"),
            {"id": documento_id},
        ).first()
        return self._documento(fila) if fila else None

    def guardar(self, documento: Documento) -> None:
        sentencia = text(
            "UPDATE documento_deuda SET estado = :estado, tipo_documento = :tipo_documento,"
            " riesgo = :riesgo, analisis_cifrado = :analisis, clave_negocio_huella = :clave,"
            " huellas_texto = :huellas, repetido_de = :repetido_de, analizado_en = :analizado_en"
            " WHERE id = :id"
        ).bindparams(bindparam("huellas", type_=ARRAY(BYTEA)))
        analisis = documento.analisis
        self._conexion.execute(
            sentencia,
            {
                "id": documento.id,
                "estado": documento.estado.value,
                "tipo_documento": documento.tipo_documento.value
                if documento.tipo_documento
                else None,
                "riesgo": analisis.riesgo.value if analisis else None,
                "analisis": self._cifrador.cifrar(
                    analisis_a_json(analisis), contexto("analisis", documento.id)
                )
                if analisis
                else None,
                "clave": documento.clave_negocio_huella,
                "huellas": list(documento.huellas_texto),
                "repetido_de": documento.repetido_de,
                "analizado_en": documento.analizado_en,
            },
        )

    def _deuda(self, condicion: str, parametros: dict[str, Any]) -> DeudaDelDocumento | None:
        fila = self._conexion.execute(
            text(
                "SELECT d.id, d.concepto, d.creado_en FROM documento_deuda doc"
                f" JOIN deuda d ON d.id = doc.deuda_id WHERE {condicion} LIMIT 1"
            ),
            parametros,
        ).first()
        return DeudaDelDocumento(fila.id, fila.concepto, fila.creado_en) if fila else None

    def deuda_con_archivo(self, gerente_id: UUID, huella: bytes) -> DeudaDelDocumento | None:
        return self._deuda(
            "doc.gerente_id = :gerente_id AND doc.huella_archivo = :huella",
            {"gerente_id": gerente_id, "huella": huella},
        )

    def deuda_con_clave(self, gerente_id: UUID, huella: bytes) -> DeudaDelDocumento | None:
        return self._deuda(
            "doc.gerente_id = :gerente_id AND doc.clave_negocio_huella = :huella",
            {"gerente_id": gerente_id, "huella": huella},
        )

    def resumen_deuda(self, deuda_id: UUID) -> DeudaDelDocumento | None:
        fila = self._conexion.execute(
            text("SELECT id, concepto, creado_en FROM deuda WHERE id = :id"), {"id": deuda_id}
        ).first()
        return DeudaDelDocumento(fila.id, fila.concepto, fila.creado_en) if fila else None

    def deudas_con_numeros(
        self, gerente_id: UUID, huellas: set[bytes]
    ) -> list[tuple[DeudaDelDocumento, set[bytes]]]:
        sentencia = text(
            "SELECT d.id, d.concepto, d.creado_en, doc.huellas_texto FROM documento_deuda doc"
            " JOIN deuda d ON d.id = doc.deuda_id"
            " WHERE doc.gerente_id = :gerente_id AND doc.huellas_texto && :huellas"
            " ORDER BY d.creado_en DESC LIMIT 50"
        ).bindparams(bindparam("huellas", type_=ARRAY(BYTEA)))
        filas = self._conexion.execute(
            sentencia, {"gerente_id": gerente_id, "huellas": list(huellas)}
        ).all()
        return [
            (
                DeudaDelDocumento(fila.id, fila.concepto, fila.creado_en),
                {bytes(h) for h in fila.huellas_texto},
            )
            for fila in filas
        ]

    def categorias(self, gerente_id: UUID) -> list[CategoriaConocida]:
        filas = self._conexion.execute(
            text(
                "SELECT nombre, descripcion FROM categoria"
                " WHERE gerente_id = :gerente_id AND archivado_en IS NULL"
                " ORDER BY nombre_normalizado"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [CategoriaConocida(fila.nombre, fila.descripcion) for fila in filas]


class RepositorioBloqueosSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    @staticmethod
    def _bloqueo(fila: Row[Any]) -> Bloqueo:
        return Bloqueo(fila.id, fila.asistente_id, fila.gerente_id, fila.bloqueado_en)

    def vigente(self, asistente_id: UUID) -> Bloqueo | None:
        fila = self._conexion.execute(
            text(
                "SELECT id, asistente_id, gerente_id, bloqueado_en FROM bloqueo_registro_deuda"
                " WHERE asistente_id = :asistente_id AND levantado_en IS NULL"
            ),
            {"asistente_id": asistente_id},
        ).first()
        return self._bloqueo(fila) if fila else None

    def vigentes_del_espacio(self, gerente_id: UUID) -> list[Bloqueo]:
        filas = self._conexion.execute(
            text(
                "SELECT id, asistente_id, gerente_id, bloqueado_en FROM bloqueo_registro_deuda"
                " WHERE gerente_id = :gerente_id AND levantado_en IS NULL ORDER BY bloqueado_en"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [self._bloqueo(fila) for fila in filas]

    def registrar_intento(self, asistente_id: UUID, deuda_id: UUID, ahora: datetime) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO intento_documento_repetido (asistente_id, deuda_id, ocurrido_en)"
                " VALUES (:asistente_id, :deuda_id, :ahora)"
            ),
            {"asistente_id": asistente_id, "deuda_id": deuda_id, "ahora": ahora},
        )

    def contar_intentos(self, asistente_id: UUID, desde: datetime) -> int:
        return int(
            self._conexion.execute(
                text(
                    "SELECT count(*) FROM intento_documento_repetido"
                    " WHERE asistente_id = :asistente_id AND ocurrido_en > :desde"
                ),
                {"asistente_id": asistente_id, "desde": desde},
            ).scalar_one()
        )

    def ultimo_levantamiento(self, asistente_id: UUID) -> datetime | None:
        valor: datetime | None = self._conexion.execute(
            text(
                "SELECT max(levantado_en) FROM bloqueo_registro_deuda"
                " WHERE asistente_id = :asistente_id"
            ),
            {"asistente_id": asistente_id},
        ).scalar_one()
        return valor

    def bloquear(self, bloqueo: Bloqueo) -> bool:
        fila = self._conexion.execute(
            text(
                "INSERT INTO bloqueo_registro_deuda (id, asistente_id, gerente_id, bloqueado_en)"
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
                "UPDATE bloqueo_registro_deuda SET levantado_en = :ahora,"
                " levantado_por = :levantado_por WHERE id = :id"
            ),
            {"id": bloqueo_id, "levantado_por": levantado_por, "ahora": ahora},
        )


class RepositorioCuentasSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._usuarios = RepositorioUsuariosSql(conexion, cifrador)

    def rol_y_gerente(self, usuario_id: UUID) -> tuple[Rol, UUID | None] | None:
        fila = self._conexion.execute(
            text("SELECT rol, gerente_id FROM usuario WHERE id = :id"), {"id": usuario_id}
        ).first()
        return (Rol(fila.rol), fila.gerente_id) if fila else None

    def bloquear_cuenta(self, usuario_id: UUID) -> bool:
        fila = self._conexion.execute(
            text("SELECT id FROM usuario WHERE id = :id FOR UPDATE"), {"id": usuario_id}
        ).first()
        return fila is not None

    def ficha(self, usuario_id: UUID) -> FichaPersonal | None:
        return self._usuarios.ficha(usuario_id)


class UnidadDocumentosSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.documentos = RepositorioDocumentosSql(self._conexion, self._cifrador)
        self.bloqueos = RepositorioBloqueosSql(self._conexion)
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
