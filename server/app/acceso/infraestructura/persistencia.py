"""Adaptadores de Postgres para los puertos del acceso (SQLAlchemy Core sobre psycopg)."""

import json
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text
from sqlalchemy.exc import IntegrityError

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.datos_personales import DatosPersonales, TipoDocumento
from app.acceso.dominio.errores import DatosDuplicados
from app.acceso.dominio.incorporacion import DocumentoLegal, Seccion, TipoDocumentoLegal
from app.acceso.dominio.modelos import CausaBloqueo, EventoAuditoria, Rol, Sesion, Usuario
from app.acceso.infraestructura.cifrado import CifradorDatos

COLUMNAS_USUARIO = """
    id, rol, gerente_id, nombre_usuario, nombres_cifrado, contrasena_hash,
    debe_cambiar_contrasena, contrasena_actualizada_en, ultimo_ingreso_en,
    intentos_fallidos, bloqueada_en, causa_bloqueo, eliminada_en, datos_confirmados_en
"""

COLUMNAS_FICHA = """
    nombres_cifrado, apellidos_cifrado, correo_cifrado, telefono_cifrado, tipo_documento,
    numero_documento_cifrado, nombre_recibos_cifrado, cargo
"""

CAMPOS_DUPLICADOS = {
    "uq_usuario_nombre_usuario": ("nombre_usuario", "Ese usuario ya está en uso."),
    "uq_usuario_correo_huella": ("correo", "Ese correo ya pertenece a otra cuenta."),
    "uq_usuario_documento_huella": (
        "numero_documento",
        "Ese documento ya pertenece a otra cuenta.",
    ),
}


def contexto(campo: str, usuario_id: UUID) -> str:
    return f"usuario.{campo}:{usuario_id}"


def duplicados(error: IntegrityError) -> DatosDuplicados | None:
    """Traduce la violación de una restricción de unicidad conocida al error del campo."""
    restriccion = getattr(error.orig, "diag", None)
    nombre = getattr(restriccion, "constraint_name", None)
    if nombre not in CAMPOS_DUPLICADOS:
        return None
    campo, mensaje = CAMPOS_DUPLICADOS[nombre]
    return DatosDuplicados(campos={campo: mensaje})


class RepositorioUsuariosSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador

    def _usuario(self, fila: Row[Any] | None) -> Usuario | None:
        if fila is None:
            return None
        return Usuario(
            id=fila.id,
            rol=Rol(fila.rol),
            gerente_id=fila.gerente_id,
            nombre_usuario=fila.nombre_usuario,
            nombres=self._cifrador.descifrar(fila.nombres_cifrado, contexto("nombres", fila.id)),
            contrasena_hash=fila.contrasena_hash,
            debe_cambiar_contrasena=fila.debe_cambiar_contrasena,
            contrasena_actualizada_en=fila.contrasena_actualizada_en,
            ultimo_ingreso_en=fila.ultimo_ingreso_en,
            intentos_fallidos=fila.intentos_fallidos,
            bloqueada_en=fila.bloqueada_en,
            causa_bloqueo=CausaBloqueo(fila.causa_bloqueo) if fila.causa_bloqueo else None,
            eliminada_en=fila.eliminada_en,
            datos_confirmados_en=fila.datos_confirmados_en,
        )

    def _buscar(self, condicion: str, parametros: dict[str, Any], bloquear: bool) -> Usuario | None:
        sql = f"SELECT {COLUMNAS_USUARIO} FROM usuario WHERE {condicion}"
        if bloquear:
            sql += " FOR UPDATE"
        return self._usuario(self._conexion.execute(text(sql), parametros).one_or_none())

    def por_nombre_usuario(self, nombre_usuario: str, *, bloquear: bool) -> Usuario | None:
        return self._buscar("nombre_usuario = :nombre", {"nombre": nombre_usuario}, bloquear)

    def por_id(self, usuario_id: UUID, *, bloquear: bool) -> Usuario | None:
        return self._buscar("id = :id", {"id": usuario_id}, bloquear)

    def existe_nombre_usuario(self, nombre_usuario: str) -> bool:
        fila = self._conexion.execute(
            text("SELECT 1 FROM usuario WHERE nombre_usuario = :nombre"),
            {"nombre": nombre_usuario},
        ).first()
        return fila is not None

    def guardar(self, usuario: Usuario) -> None:
        self._conexion.execute(
            text(
                """
                UPDATE usuario SET
                    contrasena_hash = :contrasena_hash,
                    debe_cambiar_contrasena = :debe_cambiar_contrasena,
                    contrasena_actualizada_en = :contrasena_actualizada_en,
                    ultimo_ingreso_en = :ultimo_ingreso_en,
                    intentos_fallidos = :intentos_fallidos,
                    bloqueada_en = :bloqueada_en,
                    causa_bloqueo = :causa_bloqueo,
                    eliminada_en = :eliminada_en,
                    datos_confirmados_en = :datos_confirmados_en
                WHERE id = :id
                """
            ),
            {
                "id": usuario.id,
                "contrasena_hash": usuario.contrasena_hash,
                "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
                "contrasena_actualizada_en": usuario.contrasena_actualizada_en,
                "ultimo_ingreso_en": usuario.ultimo_ingreso_en,
                "intentos_fallidos": usuario.intentos_fallidos,
                "bloqueada_en": usuario.bloqueada_en,
                "causa_bloqueo": usuario.causa_bloqueo.value if usuario.causa_bloqueo else None,
                "eliminada_en": usuario.eliminada_en,
                "datos_confirmados_en": usuario.datos_confirmados_en,
            },
        )

    def por_documento(self, tipo: TipoDocumento, numero: str) -> list[Usuario]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_USUARIO} FROM usuario"
                " WHERE tipo_documento = :tipo AND numero_documento_huella = :huella"
                " ORDER BY creado_en DESC"
            ),
            {"tipo": tipo.value, "huella": self._cifrador.huella(f"{tipo.value}:{numero}")},
        ).all()
        return [u for u in map(self._usuario, filas) if u is not None]

    def asistentes_de(self, gerente_id: UUID) -> list[tuple[Usuario, FichaPersonal]]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_USUARIO}, {COLUMNAS_FICHA} FROM usuario"
                " WHERE gerente_id = :gerente_id AND eliminada_en IS NULL"
                " ORDER BY creado_en"
            ),
            {"gerente_id": gerente_id},
        ).all()
        resultado = []
        for fila in filas:
            usuario = self._usuario(fila)
            assert usuario is not None
            resultado.append((usuario, self._ficha_de(fila, usuario.id)))
        return resultado

    def _cifrar(self, campo: str, valor: str | None, usuario_id: UUID) -> bytes | None:
        return self._cifrador.cifrar(valor, contexto(campo, usuario_id)) if valor else None

    def _columnas_datos(self, usuario_id: UUID, datos: DatosPersonales) -> dict[str, Any]:
        """Valores cifrados de los datos personales y sus huellas de unicidad."""
        documento = f"{datos.tipo_documento.value}:{datos.numero_documento}"
        return {
            "nombres": self._cifrar("nombres", datos.nombres, usuario_id),
            "apellidos": self._cifrar("apellidos", datos.apellidos, usuario_id),
            "correo": self._cifrar("correo", datos.correo, usuario_id),
            "correo_huella": self._cifrador.huella(datos.correo) if datos.correo else None,
            "telefono": self._cifrar("telefono", datos.telefono, usuario_id),
            "tipo_documento": datos.tipo_documento.value,
            "numero_documento": self._cifrar(
                "numero_documento", datos.numero_documento, usuario_id
            ),
            "numero_documento_huella": self._cifrador.huella(documento),
            "nombre_recibos": self._cifrar("nombre_recibos", datos.nombre_recibos, usuario_id),
        }

    def agregar(
        self, usuario: Usuario, datos: DatosPersonales, *, cargo: str | None = None
    ) -> None:
        try:
            self._conexion.execute(
                text(
                    """
                    INSERT INTO usuario (
                        id, rol, gerente_id, nombre_usuario, contrasena_hash,
                        nombres_cifrado, apellidos_cifrado, correo_cifrado, correo_huella,
                        telefono_cifrado, tipo_documento, numero_documento_cifrado,
                        numero_documento_huella, nombre_recibos_cifrado, cargo,
                        debe_cambiar_contrasena, contrasena_actualizada_en, datos_confirmados_en
                    ) VALUES (
                        :id, :rol, :gerente_id, :nombre_usuario, :contrasena_hash,
                        :nombres, :apellidos, :correo, :correo_huella,
                        :telefono, :tipo_documento, :numero_documento,
                        :numero_documento_huella, :nombre_recibos, :cargo,
                        :debe_cambiar_contrasena, :contrasena_actualizada_en,
                        :datos_confirmados_en
                    )
                    """
                ),
                {
                    "id": usuario.id,
                    "rol": usuario.rol.value,
                    "gerente_id": usuario.gerente_id,
                    "nombre_usuario": usuario.nombre_usuario,
                    "contrasena_hash": usuario.contrasena_hash,
                    "cargo": cargo,
                    "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
                    "contrasena_actualizada_en": usuario.contrasena_actualizada_en,
                    "datos_confirmados_en": usuario.datos_confirmados_en,
                    **self._columnas_datos(usuario.id, datos),
                },
            )
        except IntegrityError as error:
            duplicado = duplicados(error)
            if duplicado is None:
                raise
            raise duplicado from error

    def _ficha_de(self, fila: Row[Any], usuario_id: UUID) -> FichaPersonal:
        def descifrar(campo: str, valor: bytes | None) -> str | None:
            return self._cifrador.descifrar(valor, contexto(campo, usuario_id)) if valor else None

        # Los obligatorios nunca son nulos (NOT NULL); el «or ""» solo informa a mypy.
        datos = DatosPersonales(
            nombres=descifrar("nombres", fila.nombres_cifrado) or "",
            apellidos=descifrar("apellidos", fila.apellidos_cifrado) or "",
            correo=descifrar("correo", fila.correo_cifrado),
            tipo_documento=TipoDocumento(fila.tipo_documento),
            numero_documento=descifrar("numero_documento", fila.numero_documento_cifrado) or "",
            telefono=descifrar("telefono", fila.telefono_cifrado),
            nombre_recibos=descifrar("nombre_recibos", fila.nombre_recibos_cifrado),
        )
        return FichaPersonal(datos, fila.cargo)

    def ficha(self, usuario_id: UUID) -> FichaPersonal | None:
        fila = self._conexion.execute(
            text(f"SELECT {COLUMNAS_FICHA} FROM usuario WHERE id = :id"), {"id": usuario_id}
        ).one_or_none()
        return None if fila is None else self._ficha_de(fila, usuario_id)

    def actualizar_datos(self, usuario_id: UUID, datos: DatosPersonales) -> None:
        try:
            # Un savepoint: si choca con otra cuenta, la transacción sigue utilizable.
            with self._conexion.begin_nested():
                self._conexion.execute(
                    text(
                        """
                        UPDATE usuario SET
                            nombres_cifrado = :nombres,
                            apellidos_cifrado = :apellidos,
                            correo_cifrado = :correo,
                            correo_huella = :correo_huella,
                            telefono_cifrado = :telefono,
                            tipo_documento = :tipo_documento,
                            numero_documento_cifrado = :numero_documento,
                            numero_documento_huella = :numero_documento_huella,
                            nombre_recibos_cifrado = :nombre_recibos
                        WHERE id = :id
                        """
                    ),
                    {"id": usuario_id, **self._columnas_datos(usuario_id, datos)},
                )
        except IntegrityError as error:
            duplicado = duplicados(error)
            if duplicado is None:
                raise
            raise duplicado from error

    def cambiar_nombre_usuario(
        self, usuario_id: UUID, anterior: str, nuevo: str, ahora: datetime
    ) -> None:
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(
                    text("UPDATE usuario SET nombre_usuario = :nuevo WHERE id = :id"),
                    {"id": usuario_id, "nuevo": nuevo},
                )
        except IntegrityError as error:
            duplicado = duplicados(error)
            if duplicado is None:
                raise
            raise duplicado from error
        self._conexion.execute(
            text(
                "INSERT INTO cambio_nombre_usuario (usuario_id, anterior, nuevo, cambiado_en)"
                " VALUES (:usuario_id, :anterior, :nuevo, :ahora)"
            ),
            {"usuario_id": usuario_id, "anterior": anterior, "nuevo": nuevo, "ahora": ahora},
        )

    def cambios_nombre_usuario_desde(self, usuario_id: UUID, desde: datetime) -> int:
        return int(
            self._conexion.execute(
                text(
                    "SELECT count(*) FROM cambio_nombre_usuario"
                    " WHERE usuario_id = :usuario_id AND cambiado_en >= :desde"
                ),
                {"usuario_id": usuario_id, "desde": desde},
            ).scalar_one()
        )


class RepositorioSesionesSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def agregar(self, sesion: Sesion) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO sesion (id, usuario_id, token_huella, creada_en, expira_en)"
                " VALUES (:id, :usuario_id, :token_huella, :creada_en, :expira_en)"
            ),
            {
                "id": sesion.id,
                "usuario_id": sesion.usuario_id,
                "token_huella": sesion.token_huella,
                "creada_en": sesion.creada_en,
                "expira_en": sesion.expira_en,
            },
        )

    def vigente(self, token_huella: bytes, ahora: datetime) -> Sesion | None:
        fila = self._conexion.execute(
            text(
                "SELECT id, usuario_id, token_huella, creada_en, expira_en FROM sesion"
                " WHERE token_huella = :huella AND revocada_en IS NULL AND expira_en > :ahora"
            ),
            {"huella": token_huella, "ahora": ahora},
        ).one_or_none()
        if fila is None:
            return None
        return Sesion(fila.id, fila.usuario_id, fila.token_huella, fila.creada_en, fila.expira_en)

    def revocar(self, sesion_id: UUID, ahora: datetime, motivo: str) -> None:
        self._conexion.execute(
            text(
                "UPDATE sesion SET revocada_en = :ahora, motivo_revocacion = :motivo"
                " WHERE id = :id AND revocada_en IS NULL"
            ),
            {"id": sesion_id, "ahora": ahora, "motivo": motivo},
        )

    def revocar_de_usuario(
        self, usuario_id: UUID, ahora: datetime, motivo: str, *, excepto: UUID | None = None
    ) -> int:
        resultado = self._conexion.execute(
            text(
                "UPDATE sesion SET revocada_en = :ahora, motivo_revocacion = :motivo"
                " WHERE usuario_id = :usuario_id AND revocada_en IS NULL"
                " AND (CAST(:excepto AS uuid) IS NULL OR id <> CAST(:excepto AS uuid))"
            ),
            {"usuario_id": usuario_id, "ahora": ahora, "motivo": motivo, "excepto": excepto},
        )
        return resultado.rowcount


class RegistroAuditoriaSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def registrar(self, evento: EventoAuditoria) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO auditoria (accion, actor_id, cuenta_id, motivo, detalle)"
                " VALUES (:accion, :actor_id, :cuenta_id, :motivo, CAST(:detalle AS jsonb))"
            ),
            {
                "accion": evento.accion.value,
                "actor_id": evento.actor_id,
                "cuenta_id": evento.cuenta_id,
                "motivo": evento.motivo,
                "detalle": json.dumps(evento.detalle),
            },
        )


# La versión más alta de cada tipo cuya vigencia ya empezó.
VIGENTES = """
    SELECT DISTINCT ON (tipo) id, tipo, version, titulo, resumen, secciones, vigente_desde
    FROM documento_legal
    WHERE vigente_desde <= :ahora
    ORDER BY tipo, version DESC
"""


class RepositorioDocumentosLegalesSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def vigentes(self, ahora: datetime) -> list[DocumentoLegal]:
        filas = self._conexion.execute(text(VIGENTES), {"ahora": ahora}).all()
        return [
            DocumentoLegal(
                id=fila.id,
                tipo=TipoDocumentoLegal(fila.tipo),
                version=fila.version,
                titulo=fila.titulo,
                resumen=fila.resumen,
                secciones=tuple(
                    Seccion(seccion["titulo"], tuple(seccion["parrafos"]))
                    for seccion in fila.secciones
                ),
                vigente_desde=fila.vigente_desde,
            )
            for fila in filas
        ]

    def aceptaciones(self, usuario_id: UUID, documento_ids: list[int]) -> dict[int, datetime]:
        if not documento_ids:
            return {}
        filas = self._conexion.execute(
            text(
                "SELECT documento_id, aceptada_en FROM aceptacion_documento"
                " WHERE usuario_id = :usuario_id AND documento_id = ANY(:ids)"
            ),
            {"usuario_id": usuario_id, "ids": documento_ids},
        ).all()
        return {fila.documento_id: fila.aceptada_en for fila in filas}

    def hay_sin_aceptar(self, usuario_id: UUID, ahora: datetime) -> bool:
        fila = self._conexion.execute(
            text(
                f"SELECT EXISTS (SELECT 1 FROM ({VIGENTES}) vigente WHERE NOT EXISTS ("
                "SELECT 1 FROM aceptacion_documento aceptacion"
                " WHERE aceptacion.documento_id = vigente.id"
                " AND aceptacion.usuario_id = :usuario_id))"
            ),
            {"usuario_id": usuario_id, "ahora": ahora},
        ).scalar_one()
        return bool(fila)

    def registrar_aceptacion(self, usuario_id: UUID, documento_id: int, ahora: datetime) -> bool:
        insertada = self._conexion.execute(
            text(
                "INSERT INTO aceptacion_documento (usuario_id, documento_id, aceptada_en)"
                " VALUES (:usuario_id, :documento_id, :ahora)"
                " ON CONFLICT ON CONSTRAINT uq_aceptacion_documento_usuario_documento DO NOTHING"
                " RETURNING id"
            ),
            {"usuario_id": usuario_id, "documento_id": documento_id, "ahora": ahora},
        ).first()
        return insertada is not None


class UnidadDeTrabajoSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.usuarios = RepositorioUsuariosSql(self._conexion, self._cifrador)
        self.sesiones = RepositorioSesionesSql(self._conexion)
        self.auditoria = RegistroAuditoriaSql(self._conexion)
        self.documentos = RepositorioDocumentosLegalesSql(self._conexion)
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
