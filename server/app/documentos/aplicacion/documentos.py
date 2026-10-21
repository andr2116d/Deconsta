"""Casos de uso de los documentos de las deudas.

Subir: el gerente y sus asistentes suben el documento al espacio del gerente (sale de la sesión,
nunca del cliente). Se valida el archivo por su contenido, se rechaza el que ya respalda otra deuda
y se guarda cifrado; el análisis corre después en el worker.

Un documento solo lo ve quien lo subió y el gerente del espacio; cualquier otro responde igual que
uno inexistente.
"""

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import exigir_cupo
from app.acceso.dominio.errores import ServicioNoDisponible, SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite, Reloj
from app.categorias.aplicacion.categorias import espacio_de
from app.documentos.dominio.analisis import (
    NO_ES_DEUDA,
    clave_negocio,
    contrastar,
    estado_tras_analisis,
    evaluar_metadatos,
    mismos_numeros,
    numeros_largos,
    senal_ilegible,
    senal_legibilidad,
    senal_naturaleza,
    senal_naturaleza_lectura,
    senal_revision_incompleta,
    senal_veredicto,
)
from app.documentos.dominio.archivos import limpiar_nombre, validar_archivo
from app.documentos.dominio.bloqueos import MAXIMO_REPETIDOS, Bloqueo, contar_desde
from app.documentos.dominio.errores import (
    AsistenteNoEncontrada,
    BloqueoNoEncontrado,
    ContenidoNoDisponible,
    DocumentoNoEncontrado,
    DocumentoYaRegistrado,
    RegistroBloqueado,
)
from app.documentos.dominio.modelos import (
    Analisis,
    DatosLeidos,
    DeudaDelDocumento,
    Documento,
    EstadoDocumento,
    Senal,
    TipoArchivo,
)
from app.documentos.dominio.puertos import (
    Almacen,
    ColaAnalisis,
    ErrorAlmacen,
    ErrorCola,
    ErrorRevision,
    FabricaUnidadDocumentos,
    Huellero,
    InspectorArchivos,
    LectorTexto,
    RevisorIa,
    UnidadDocumentos,
)
from app.notificaciones.aplicacion.notificaciones import Avisos
from app.notificaciones.dominio.modelos import TipoNotificacion, nueva_notificacion
from app.notificaciones.dominio.puertos import PublicadorAvisos

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentoConsultado:
    documento: Documento
    # Deuda que ya usa este documento, si resultó repetido.
    repetido_de: DeudaDelDocumento | None


def huella_archivo(huellero: Huellero, contenido: bytes) -> bytes:
    return huellero.huella(f"archivo:{hashlib.sha256(contenido).hexdigest()}")


def anotar_repetido(
    uow: UnidadDocumentos,
    avisos: Avisos,
    reloj: Reloj,
    asistente_id: UUID,
    gerente_id: UUID,
    deuda: DeudaDelDocumento,
) -> bool:
    """Deja constancia del intento y, si es el tercero en 24 horas, bloquea el registro de deudas
    de la asistente y avisa a su gerente. Devuelve True si quedó bloqueada."""
    ahora = reloj()
    uow.bloqueos.registrar_intento(asistente_id, deuda.id, ahora)
    uow.auditoria.registrar(
        EventoAuditoria(
            Accion.DOCUMENTO_REPETIDO,
            actor_id=asistente_id,
            detalle={"deuda_id": str(deuda.id)},
        )
    )
    desde = contar_desde(ahora, uow.bloqueos.ultimo_levantamiento(asistente_id))
    if uow.bloqueos.contar_intentos(asistente_id, desde) < MAXIMO_REPETIDOS:
        return False
    bloqueo = Bloqueo(uuid4(), asistente_id, gerente_id, ahora)
    if not uow.bloqueos.bloquear(bloqueo):
        return True
    uow.auditoria.registrar(
        EventoAuditoria(
            Accion.REGISTRO_DEUDAS_BLOQUEADO,
            cuenta_id=asistente_id,
            detalle={"intentos": MAXIMO_REPETIDOS},
        )
    )
    avisos.guardar(
        uow.notificaciones,
        nueva_notificacion(
            gerente_id,
            TipoNotificacion.REGISTRO_BLOQUEADO,
            f"bloqueo:{bloqueo.id}",
            "Bloqueamos el registro de deudas de tu asistente",
            f"Intentó {MAXIMO_REPETIDOS} veces en 24 horas registrar documentos que ya respaldan "
            "otras deudas. Revisa lo ocurrido y, si corresponde, permítele registrar otra vez "
            "desde Mi equipo.",
            ahora,
            cuenta_id=asistente_id,
        ),
    )
    return True


class _OperacionDocumentos:
    def __init__(
        self,
        unidad: FabricaUnidadDocumentos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
    ) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._publicador = publicador

    @staticmethod
    def _visible(uow: UnidadDocumentos, sesion: SesionActiva, documento_id: UUID) -> Documento:
        documento = uow.documentos.por_id(documento_id)
        usuario = sesion.usuario
        if (
            documento is None
            or documento.gerente_id != espacio_de(sesion)
            or (usuario.rol is not Rol.GERENTE and documento.subido_por != usuario.id)
        ):
            raise DocumentoNoEncontrado()
        return documento


class SubirDocumento(_OperacionDocumentos):
    def __init__(
        self,
        unidad: FabricaUnidadDocumentos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        *,
        almacen: Almacen,
        inspector: InspectorArchivos,
        huellero: Huellero,
        cola: ColaAnalisis,
        limitador: LimitadorSolicitudes,
        limite: Limite,
    ) -> None:
        super().__init__(unidad, reloj, publicador)
        self._almacen = almacen
        self._inspector = inspector
        self._huellero = huellero
        self._cola = cola
        self._limitador = limitador
        self._limite = limite

    def ejecutar(self, sesion: SesionActiva, contenido: bytes, nombre: str | None) -> Documento:
        usuario = sesion.usuario
        gerente_id = espacio_de(sesion)
        exigir_cupo(self._limitador, (self._limite, str(usuario.id)))
        tipo = validar_archivo(contenido)
        examen = self._inspector.examinar(contenido, tipo)
        huella = huella_archivo(self._huellero, contenido)
        avisos = Avisos(self._publicador)
        repetido: DocumentoYaRegistrado | None = None
        with self._unidad() as uow:
            asistente = usuario.rol is Rol.ASISTENTE
            if asistente:
                uow.cuentas.bloquear_cuenta(usuario.id)
                if bloqueo := uow.bloqueos.vigente(usuario.id):
                    raise RegistroBloqueado(bloqueo.bloqueado_en)
            if deuda := uow.documentos.deuda_con_archivo(gerente_id, huella):
                bloqueado = asistente and anotar_repetido(
                    uow, avisos, self._reloj, usuario.id, gerente_id, deuda
                )
                repetido = DocumentoYaRegistrado(deuda, registro_bloqueado=bloqueado)
            else:
                documento = self._guardar(
                    uow, sesion, gerente_id, contenido, tipo, nombre, examen.paginas, huella
                )
        # El intento repetido queda guardado aunque la respuesta sea un error.
        avisos.enviar()
        if repetido:
            raise repetido
        try:
            self._cola.encolar(documento.id)
        except ErrorCola as error:
            with self._unidad() as uow:
                documento.estado = EstadoDocumento.FALLIDO
                uow.documentos.guardar(documento)
            raise ServicioNoDisponible() from error
        return documento

    def _guardar(
        self,
        uow: UnidadDocumentos,
        sesion: SesionActiva,
        gerente_id: UUID,
        contenido: bytes,
        tipo: TipoArchivo,
        nombre: str | None,
        paginas: int,
        huella: bytes,
    ) -> Documento:
        documento_id = uuid4()
        clave = f"documentos/{gerente_id}/{documento_id}"
        try:
            self._almacen.guardar(clave, contenido, tipo)
        except ErrorAlmacen as error:
            raise ServicioNoDisponible() from error
        documento = Documento(
            id=documento_id,
            gerente_id=gerente_id,
            subido_por=sesion.usuario.id,
            tipo_archivo=tipo,
            tamano=len(contenido),
            paginas=paginas,
            nombre_archivo=limpiar_nombre(nombre, tipo),
            clave_objeto=clave,
            huella_archivo=huella,
            estado=EstadoDocumento.ANALIZANDO,
            subido_en=self._reloj(),
        )
        uow.documentos.agregar(documento)
        return documento


class AnalizarDocumento(_OperacionDocumentos):
    """Lo ejecuta el worker. Si se repite para un documento ya analizado, no hace nada."""

    def __init__(
        self,
        unidad: FabricaUnidadDocumentos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        *,
        almacen: Almacen,
        inspector: InspectorArchivos,
        lector: LectorTexto,
        revisor: RevisorIa,
        huellero: Huellero,
    ) -> None:
        super().__init__(unidad, reloj, publicador)
        self._almacen = almacen
        self._inspector = inspector
        self._lector = lector
        self._revisor = revisor
        self._huellero = huellero

    def ejecutar(self, documento_id: UUID) -> EstadoDocumento | None:
        with self._unidad() as uow:
            documento = uow.documentos.por_id(documento_id)
            if documento is None or documento.estado is not EstadoDocumento.ANALIZANDO:
                return None
            cuenta = uow.cuentas.rol_y_gerente(documento.subido_por)
            categorias = uow.documentos.categorias(documento.gerente_id)
        rol = cuenta[0] if cuenta else Rol.ASISTENTE
        contenido = self._almacen.leer(documento.clave_objeto)
        tipo = documento.tipo_archivo
        senales: list[Senal] = evaluar_metadatos(
            self._inspector.examinar(contenido, tipo).metadatos
        )
        lectura = self._lector.leer(contenido, tipo)
        datos: DatosLeidos | None = None
        ilegible = senal_legibilidad(lectura)
        # Un comprobante de pago o un documento de identidad no llega a la IA: no es una deuda.
        naturaleza = None if ilegible else senal_naturaleza_lectura(lectura)
        if naturaleza:
            senales.append(naturaleza)
        elif ilegible is None:
            try:
                revision = self._revisor.revisar(contenido, tipo, lectura, categorias)
            except ErrorRevision:
                logger.warning("La revisión con IA del documento %s no se completó", documento_id)
                senales.append(senal_revision_incompleta())
            else:
                if revision.legible:
                    datos = revision.datos
                    if no_es := senal_naturaleza(datos, revision.motivos):
                        senales.append(no_es)
                    senales.extend(contrastar(datos, lectura))
                    if veredicto := senal_veredicto(revision.veredicto, revision.motivos):
                        senales.append(veredicto)
                else:
                    ilegible = senal_ilegible()
        if ilegible:
            senales.insert(0, ilegible)
        analisis = Analisis(datos, tuple(senales))
        numeros = {self._huellero.huella(f"numero:{n}") for n in numeros_largos(lectura.texto)}
        clave = clave_negocio(datos) if datos else None
        huella_clave = self._huellero.huella(f"clave:{clave}") if clave else None
        return self._concluir(
            documento_id, rol, analisis, ilegible is not None, numeros, huella_clave
        )

    def _concluir(
        self,
        documento_id: UUID,
        rol: Rol,
        analisis: Analisis,
        ilegible: bool,
        numeros: set[bytes],
        huella_clave: bytes | None,
    ) -> EstadoDocumento | None:
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            documento = uow.documentos.por_id(documento_id, bloquear=True)
            if documento is None or documento.estado is not EstadoDocumento.ANALIZANDO:
                return None
            # Lo que no es una deuda no se compara: el comprobante del pago de un recibo comparte
            # sus números y no debe contar como el recibo repetido.
            no_es_deuda = any(s.codigo in NO_ES_DEUDA for s in analisis.senales)
            repetido = (
                None
                if ilegible or no_es_deuda
                else self._repetido(uow, documento, numeros, huella_clave)
            )
            if ilegible:
                documento.estado = EstadoDocumento.ILEGIBLE
            elif repetido:
                documento.estado = EstadoDocumento.REPETIDO
                documento.repetido_de = repetido.id
                if rol is Rol.ASISTENTE:
                    uow.cuentas.bloquear_cuenta(documento.subido_por)
                    anotar_repetido(
                        uow,
                        avisos,
                        self._reloj,
                        documento.subido_por,
                        documento.gerente_id,
                        repetido,
                    )
            else:
                documento.estado = estado_tras_analisis(analisis, rol)
            documento.analisis = analisis
            documento.analizado_en = self._reloj()
            documento.huellas_texto = tuple(sorted(numeros))
            documento.clave_negocio_huella = huella_clave
            documento.tipo_documento = analisis.datos.tipo if analisis.datos else None
            uow.documentos.guardar(documento)
        avisos.enviar()
        return documento.estado

    @staticmethod
    def _repetido(
        uow: UnidadDocumentos,
        documento: Documento,
        numeros: set[bytes],
        huella_clave: bytes | None,
    ) -> DeudaDelDocumento | None:
        if huella_clave and (
            deuda := uow.documentos.deuda_con_clave(documento.gerente_id, huella_clave)
        ):
            return deuda
        if not numeros:
            return None
        for deuda, ajenos in uow.documentos.deudas_con_numeros(documento.gerente_id, numeros):
            if mismos_numeros(numeros, ajenos):
                return deuda
        return None


class MarcarAnalisisFallido(_OperacionDocumentos):
    """Cuando el worker agota sus reintentos: el documento no queda «analizando» para siempre."""

    def ejecutar(self, documento_id: UUID) -> None:
        with self._unidad() as uow:
            documento = uow.documentos.por_id(documento_id, bloquear=True)
            if documento is None or documento.estado is not EstadoDocumento.ANALIZANDO:
                return
            documento.estado = EstadoDocumento.FALLIDO
            documento.analizado_en = self._reloj()
            uow.documentos.guardar(documento)


class ConsultarDocumento(_OperacionDocumentos):
    def ejecutar(self, sesion: SesionActiva, documento_id: UUID) -> DocumentoConsultado:
        with self._unidad() as uow:
            documento = self._visible(uow, sesion, documento_id)
            repetido = (
                uow.documentos.resumen_deuda(documento.repetido_de)
                if documento.repetido_de
                else None
            )
            return DocumentoConsultado(documento, repetido)


@dataclass(frozen=True)
class ContenidoDocumento:
    contenido: bytes
    tipo: TipoArchivo
    nombre: str


class LeerContenido(_OperacionDocumentos):
    def __init__(
        self,
        unidad: FabricaUnidadDocumentos,
        reloj: Reloj,
        publicador: PublicadorAvisos,
        *,
        almacen: Almacen,
    ) -> None:
        super().__init__(unidad, reloj, publicador)
        self._almacen = almacen

    def ejecutar(self, sesion: SesionActiva, documento_id: UUID) -> ContenidoDocumento:
        with self._unidad() as uow:
            documento = self._visible(uow, sesion, documento_id)
        try:
            contenido = self._almacen.leer(documento.clave_objeto)
        except ErrorAlmacen as error:
            logger.error("No se pudo leer el archivo del documento %s", documento_id)
            raise ContenidoNoDisponible() from error
        return ContenidoDocumento(contenido, documento.tipo_archivo, documento.nombre_archivo)


class _OperacionBloqueos(_OperacionDocumentos):
    @staticmethod
    def _exigir_gerente(sesion: SesionActiva) -> UUID:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        return sesion.usuario.id


class ListarBloqueos(_OperacionBloqueos):
    def ejecutar(self, sesion: SesionActiva) -> list[Bloqueo]:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            return uow.bloqueos.vigentes_del_espacio(gerente_id)


class LevantarBloqueo(_OperacionBloqueos):
    def ejecutar(self, sesion: SesionActiva, asistente_id: UUID) -> None:
        gerente_id = self._exigir_gerente(sesion)
        avisos = Avisos(self._publicador)
        with self._unidad() as uow:
            cuenta = uow.cuentas.rol_y_gerente(asistente_id)
            if cuenta is None or cuenta != (Rol.ASISTENTE, gerente_id):
                raise AsistenteNoEncontrada()
            uow.cuentas.bloquear_cuenta(asistente_id)
            bloqueo = uow.bloqueos.vigente(asistente_id)
            if bloqueo is None:
                raise BloqueoNoEncontrado()
            ahora = self._reloj()
            uow.bloqueos.levantar(bloqueo.id, gerente_id, ahora)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.REGISTRO_DEUDAS_DESBLOQUEADO, actor_id=gerente_id, cuenta_id=asistente_id
                )
            )
            avisos.guardar(
                uow.notificaciones,
                nueva_notificacion(
                    asistente_id,
                    TipoNotificacion.REGISTRO_DESBLOQUEADO,
                    f"bloqueo:{bloqueo.id}:levantado",
                    "Ya puedes registrar deudas",
                    "Tu gerente te permitió registrar deudas otra vez. Recuerda que cada documento "
                    "respalda una sola deuda.",
                    ahora,
                    cuenta_id=asistente_id,
                ),
            )
        avisos.enviar()
