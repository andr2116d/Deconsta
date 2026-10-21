"""Casos de uso de las reglas de autorización («Límites y categorías»).

Solo el gerente las consulta y las cambia: el espacio sale siempre de la sesión y un titular de
otro espacio responde igual que uno inexistente. Cada escritura toma la fila del gerente con FOR
UPDATE, cuenta para el límite de intentos y queda en la auditoría sin datos personales de terceros
(solo qué cambió, nunca nombres ni documentos).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import exigir_cupo
from app.acceso.dominio.datos_personales import TipoDocumento
from app.acceso.dominio.errores import NoAutenticado, SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite, Reloj
from app.reglas.dominio.errores import (
    AutorizacionNoDeclarada,
    LimiteTitulares,
    ReglaInvalida,
    SinCambios,
    TitularDuplicado,
    TitularEsGerente,
    TitularNoEncontrado,
)
from app.reglas.dominio.evaluacion import Evaluacion, Identidad, TitularDelDocumento, evaluar
from app.reglas.dominio.importes import a_importe, error_importe
from app.reglas.dominio.puertos import FabricaUnidadReglas, ReglaAutorizacion, UnidadReglas
from app.reglas.dominio.titulares import (
    MAXIMO_TITULARES,
    DatosTitular,
    Documento,
    TipoDocumentoTitular,
    TitularAutorizado,
    clave_nombre,
    documento_de,
    limpiar,
    validar_nombre,
    validar_relacion,
)


@dataclass(frozen=True)
class ReglasDelEspacio:
    regla: ReglaAutorizacion | None
    titulares: list[TitularAutorizado]


@dataclass(frozen=True)
class NuevoTitular:
    nombre: str
    tipo_documento: str | None = None
    numero_documento: str | None = None
    relacion: str | None = None
    autorizacion_declarada: bool = False


@dataclass(frozen=True)
class DocumentoPorEvaluar:
    importe: str
    titular_nombre: str | None = None
    titular_tipo_documento: str | None = None
    titular_numero_documento: str | None = None


def identidad_gerente(uow: UnidadReglas, gerente_id: UUID) -> Identidad | None:
    """El gerente, con su nombre completo y el nombre con que figura en sus recibos."""
    ficha = uow.reglas.ficha_gerente(gerente_id)
    if ficha is None:
        return None
    datos = ficha.datos
    tipo = (
        TipoDocumentoTitular.DNI
        if datos.tipo_documento is TipoDocumento.DNI
        else TipoDocumentoTitular.CARNE_EXTRANJERIA
    )
    nombres = (f"{datos.nombres} {datos.apellidos}",) + (
        (datos.nombre_recibos,) if datos.nombre_recibos else ()
    )
    return Identidad(nombres, Documento(tipo, datos.numero_documento), "Tú")


def identidades(uow: UnidadReglas, gerente_id: UUID) -> list[Identidad]:
    """Quienes no piden autorización por titular: el gerente y sus titulares autorizados."""
    gerente = identidad_gerente(uow, gerente_id)
    return ([gerente] if gerente else []) + [
        Identidad((t.nombre,), t.documento, t.relacion or t.nombre)
        for t in uow.reglas.titulares(gerente_id)
    ]


class _OperacionReglas:
    def __init__(
        self,
        unidad: FabricaUnidadReglas,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        reloj: Reloj,
    ) -> None:
        self._unidad = unidad
        self._limitador = limitador
        self._limite = limite
        self._reloj = reloj

    def _exigir_gerente(self, sesion: SesionActiva, *, limitar: bool = True) -> UUID:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        if limitar:
            exigir_cupo(self._limitador, (self._limite, str(sesion.usuario.id)))
        return sesion.usuario.id

    @staticmethod
    def _bloquear(uow: UnidadReglas, gerente_id: UUID) -> None:
        if not uow.reglas.bloquear_espacio(gerente_id):
            raise NoAutenticado()

    @staticmethod
    def _titular(uow: UnidadReglas, gerente_id: UUID, titular_id: UUID) -> TitularAutorizado:
        titular = uow.reglas.titular(gerente_id, titular_id)
        if titular is None:
            raise TitularNoEncontrado()
        return titular

    @staticmethod
    def _exigir_nombre_libre(
        uow: UnidadReglas, gerente_id: UUID, nombre: str, propio: UUID | None = None
    ) -> None:
        clave = clave_nombre(nombre)
        if any(
            t.id != propio and clave_nombre(t.nombre) == clave
            for t in uow.reglas.titulares(gerente_id)
        ):
            raise TitularDuplicado("nombre")

    @staticmethod
    def _auditar(
        uow: UnidadReglas,
        accion: Accion,
        sesion: SesionActiva,
        motivo: str | None = None,
        **detalle: object,
    ) -> None:
        uow.auditoria.registrar(
            EventoAuditoria(accion, actor_id=sesion.usuario.id, motivo=motivo, detalle=detalle)
        )


class ConsultarReglas(_OperacionReglas):
    def ejecutar(self, sesion: SesionActiva) -> ReglasDelEspacio:
        gerente_id = self._exigir_gerente(sesion, limitar=False)
        with self._unidad() as uow:
            return ReglasDelEspacio(uow.reglas.regla(gerente_id), uow.reglas.titulares(gerente_id))


class CambiarLimite(_OperacionReglas):
    def ejecutar(self, sesion: SesionActiva, limite: str | None) -> ReglaAutorizacion:
        """Con un importe fija el límite; con None lo quita (el importe deja de detener deudas)."""
        gerente_id = self._exigir_gerente(sesion)
        nuevo: Decimal | None = None
        if limite is not None:
            if mensaje := error_importe(limite):
                raise ReglaInvalida(campos={"limite_importe": mensaje})
            nuevo = a_importe(limite)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            actual = uow.reglas.regla(gerente_id)
            anterior = actual.limite_importe if actual else None
            if anterior == nuevo:
                raise SinCambios()
            guardada = uow.reglas.guardar_limite(gerente_id, nuevo, sesion.usuario.id)
            self._auditar(
                uow,
                Accion.LIMITE_AUTORIZACION_CAMBIADO,
                sesion,
                antes=str(anterior) if anterior is not None else None,
                despues=str(nuevo) if nuevo is not None else None,
            )
            return guardada


class AgregarTitular(_OperacionReglas):
    def ejecutar(self, sesion: SesionActiva, nuevo: NuevoTitular) -> TitularAutorizado:
        gerente_id = self._exigir_gerente(sesion)
        datos = DatosTitular.crear(
            nombre=nuevo.nombre,
            tipo_documento=nuevo.tipo_documento,
            numero_documento=nuevo.numero_documento,
            relacion=nuevo.relacion,
        )
        # Ley 29733: sus datos solo se registran con su autorización.
        if not nuevo.autorizacion_declarada:
            raise AutorizacionNoDeclarada()
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            gerente = identidad_gerente(uow, gerente_id)
            if datos.documento and gerente and gerente.reconoce(None, datos.documento):
                raise TitularEsGerente()
            vigentes = uow.reglas.titulares(gerente_id)
            if len(vigentes) >= MAXIMO_TITULARES:
                raise LimiteTitulares(MAXIMO_TITULARES)
            self._exigir_nombre_libre(uow, gerente_id, datos.nombre)
            ahora = self._reloj()
            titular = TitularAutorizado(
                id=uuid4(),
                gerente_id=gerente_id,
                nombre=datos.nombre,
                documento=datos.documento,
                relacion=datos.relacion,
                autorizacion_declarada_en=ahora,
                creado_por=sesion.usuario.id,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            uow.reglas.agregar_titular(titular)
            self._auditar(
                uow,
                Accion.TITULAR_AUTORIZADO_AGREGADO,
                sesion,
                titular_id=str(titular.id),
                tipo_documento=datos.documento.tipo.value if datos.documento else None,
            )
            return titular


class EditarTitular(_OperacionReglas):
    """Cambia el nombre y la relación. El documento no se edita: se quita y se agrega otro."""

    def ejecutar(
        self, sesion: SesionActiva, titular_id: UUID, nombre: str, relacion: str | None
    ) -> TitularAutorizado:
        gerente_id = self._exigir_gerente(sesion)
        errores: dict[str, str] = {}
        limpio = validar_nombre(nombre, errores)
        relacion_limpia = validar_relacion(relacion, errores)
        if errores:
            raise ReglaInvalida(campos=errores)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            titular = self._titular(uow, gerente_id, titular_id)
            cambios = [
                campo
                for campo, antes, despues in (
                    ("nombre", titular.nombre, limpio),
                    ("relacion", titular.relacion, relacion_limpia),
                )
                if antes != despues
            ]
            if not cambios:
                raise SinCambios()
            self._exigir_nombre_libre(uow, gerente_id, limpio, propio=titular.id)
            titular.nombre, titular.relacion = limpio, relacion_limpia
            titular.actualizado_en = self._reloj()
            uow.reglas.guardar_titular(titular)
            self._auditar(
                uow,
                Accion.TITULAR_AUTORIZADO_EDITADO,
                sesion,
                titular_id=str(titular.id),
                campos=cambios,
            )
            return titular


class QuitarTitular(_OperacionReglas):
    """Baja lógica: sus recibos vuelven a pedir autorización; la auditoría se conserva."""

    def ejecutar(self, sesion: SesionActiva, titular_id: UUID, motivo: str | None) -> None:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            titular = self._titular(uow, gerente_id, titular_id)
            titular.quitado_en = self._reloj()
            uow.reglas.guardar_titular(titular)
            self._auditar(
                uow,
                Accion.TITULAR_AUTORIZADO_QUITADO,
                sesion,
                motivo,
                titular_id=str(titular.id),
            )


class EvaluarDocumento(_OperacionReglas):
    """Prueba las reglas como si una asistente registrara el documento. No guarda nada: el
    registro de deudas aplicará la misma evaluación."""

    def ejecutar(self, sesion: SesionActiva, documento: DocumentoPorEvaluar) -> Evaluacion:
        gerente_id = self._exigir_gerente(sesion)
        errores: dict[str, str] = {}
        if mensaje := error_importe(documento.importe):
            errores["importe"] = mensaje
        titular = TitularDelDocumento(
            limpiar(documento.titular_nombre or "") or None,
            documento_de(
                documento.titular_tipo_documento, documento.titular_numero_documento, errores
            ),
        )
        if errores:
            raise ReglaInvalida(campos=errores)
        with self._unidad() as uow:
            regla = uow.reglas.regla(gerente_id)
            return evaluar(
                registra=Rol.ASISTENTE,
                importe=a_importe(documento.importe),
                limite=regla.limite_importe if regla else None,
                titular=titular,
                identidades=identidades(uow, gerente_id),
            )
