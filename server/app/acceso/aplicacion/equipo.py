"""Casos de uso de «Mi equipo»: el gerente administra las cuentas de sus asistentes.

Solo un gerente puede usarlos y solo sobre las asistentes de su equipo: una asistente de otro equipo
responde igual que una inexistente. Cada operación toma la fila del gerente con FOR UPDATE, así dos
operaciones simultáneas sobre el mismo equipo se atienden una tras otra. Nada se borra: eliminar es
una baja lógica que conserva el historial y permite recuperar la cuenta.

El trabajo (deudas y pagos) pertenecerá al equipo y no a una asistente concreta: al eliminar a una,
lo pendiente sigue disponible para las demás y para las que se registren después.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.crear_cuenta import elegir_nombre_usuario, generar_contrasena_temporal
from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.dominio import politica_contrasena
from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.dominio.datos_personales import DatosPersonales, validar_cargo
from app.acceso.dominio.errores import (
    AsistenteEliminadaRegistrada,
    ContrasenaInsegura,
    CuentaNoBloqueada,
    CuentaNoEliminada,
    CuentaNoEncontrada,
    CuentaYaBloqueada,
    DatosDuplicados,
    NoAutenticado,
    PersonaYaEnEquipo,
    SinPermiso,
)
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol, Usuario
from app.acceso.dominio.puertos import (
    FabricaUnidadDeTrabajo,
    LimitadorSolicitudes,
    ProtectorContrasenas,
    Reloj,
    UnidadDeTrabajo,
)

DOCUMENTO_DE_OTRA_CUENTA = "Ese documento ya pertenece a otra cuenta."


@dataclass(frozen=True)
class MiembroEquipo:
    usuario: Usuario
    ficha: FichaPersonal


@dataclass(frozen=True)
class CredencialesEntregadas:
    """La contraseña temporal solo existe en esta respuesta: luego queda únicamente su hash."""

    miembro: MiembroEquipo
    contrasena: str


@dataclass(frozen=True)
class NuevaAsistente:
    datos: DatosPersonales
    cargo: str | None = None
    # Vacíos: Deconsta los genera.
    nombre_usuario: str | None = None
    contrasena: str | None = None
    # Si esa persona fue eliminada de este equipo, el gerente ya eligió crear una cuenta nueva.
    crear_aunque_eliminada: bool = False


class _OperacionEquipo:
    def __init__(
        self,
        unidad: FabricaUnidadDeTrabajo,
        contrasenas: ProtectorContrasenas,
        limitador: LimitadorSolicitudes,
        limites: LimitesAcceso,
        reloj: Reloj,
    ) -> None:
        self._unidad = unidad
        self._contrasenas = contrasenas
        self._limitador = limitador
        self._limites = limites
        self._reloj = reloj

    def _exigir_gerente(self, sesion: SesionActiva, *, limitar: bool = True) -> None:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        if limitar:
            exigir_cupo(self._limitador, (self._limites.gestion_equipo, str(sesion.usuario.id)))

    @staticmethod
    def _gerente(uow: UnidadDeTrabajo, sesion: SesionActiva) -> Usuario:
        gerente = uow.usuarios.por_id(sesion.usuario.id, bloquear=True)
        if gerente is None or gerente.rol is not Rol.GERENTE:
            raise NoAutenticado()
        return gerente

    @staticmethod
    def _asistente(
        uow: UnidadDeTrabajo, gerente: Usuario, asistente_id: UUID, *, eliminada: bool = False
    ) -> Usuario:
        asistente = uow.usuarios.por_id(asistente_id, bloquear=True)
        # Otro equipo, otro rol o una eliminada (salvo al recuperarla) responden igual: no existe.
        if (
            asistente is None
            or asistente.rol is not Rol.ASISTENTE
            or asistente.gerente_id != gerente.id
            or (asistente.eliminada and not eliminada)
        ):
            raise CuentaNoEncontrada()
        return asistente

    @staticmethod
    def _miembro(uow: UnidadDeTrabajo, usuario: Usuario) -> MiembroEquipo:
        ficha = uow.usuarios.ficha(usuario.id)
        assert ficha is not None
        return MiembroEquipo(usuario, ficha)


class ListarEquipo(_OperacionEquipo):
    def ejecutar(self, sesion: SesionActiva) -> list[MiembroEquipo]:
        self._exigir_gerente(sesion, limitar=False)
        with self._unidad() as uow:
            return [MiembroEquipo(u, f) for u, f in uow.usuarios.asistentes_de(sesion.usuario.id)]


class RegistrarAsistente(_OperacionEquipo):
    def ejecutar(self, sesion: SesionActiva, nueva: NuevaAsistente) -> CredencialesEntregadas:
        self._exigir_gerente(sesion)
        cargo = validar_cargo(nueva.cargo)
        datos = nueva.datos
        with self._unidad() as uow:
            ahora = self._reloj()
            gerente = self._gerente(uow, sesion)
            self._revisar_documento(uow, gerente, datos, nueva.crear_aunque_eliminada)
            nombre = elegir_nombre_usuario(uow, nueva.nombre_usuario, datos)
            contrasena = nueva.contrasena
            if contrasena:
                incumplidos = politica_contrasena.evaluar(contrasena, nombre_usuario=nombre)
                if incumplidos:
                    raise ContrasenaInsegura(incumplidos, campo="contrasena")
            else:
                contrasena = generar_contrasena_temporal(nombre)
            usuario = Usuario(
                id=uuid4(),
                rol=Rol.ASISTENTE,
                gerente_id=gerente.id,
                nombre_usuario=nombre,
                nombres=datos.nombres,
                contrasena_hash=self._contrasenas.generar_hash(contrasena),
                # Su gerente conoce esta contraseña: se le recordará cambiarla en cada ingreso.
                debe_cambiar_contrasena=True,
                contrasena_actualizada_en=ahora,
                ultimo_ingreso_en=None,
                intentos_fallidos=0,
                bloqueada_en=None,
            )
            uow.usuarios.agregar(usuario, datos, cargo=cargo)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_CREADA,
                    actor_id=gerente.id,
                    cuenta_id=usuario.id,
                    detalle={
                        "rol": Rol.ASISTENTE.value,
                        "origen": "mi_equipo",
                        "usuario_generado": not nueva.nombre_usuario,
                        "contrasena_generada": not nueva.contrasena,
                        "tras_eliminada": nueva.crear_aunque_eliminada,
                    },
                )
            )
            miembro = self._miembro(uow, usuario)
        return CredencialesEntregadas(miembro, contrasena)

    @staticmethod
    def _revisar_documento(
        uow: UnidadDeTrabajo, gerente: Usuario, datos: DatosPersonales, crear_aunque_eliminada: bool
    ) -> None:
        """Una persona no puede tener dos cuentas vigentes. Si este gerente la eliminó antes, se le
        ofrece recuperarla en vez de crear otra."""
        existentes = uow.usuarios.por_documento(datos.tipo_documento, datos.numero_documento)
        for cuenta in existentes:
            if cuenta.eliminada:
                continue
            if cuenta.rol is Rol.ASISTENTE and cuenta.gerente_id == gerente.id:
                raise PersonaYaEnEquipo(bloqueada=cuenta.bloqueada)
            # De otro equipo o de un gerente: no se revela de quién es.
            raise DatosDuplicados(campos={"numero_documento": DOCUMENTO_DE_OTRA_CUENTA})
        eliminada = next((c for c in existentes if c.gerente_id == gerente.id), None)
        if eliminada is not None and not crear_aunque_eliminada:
            raise AsistenteEliminadaRegistrada(eliminada.id, eliminada.nombre_usuario)


class BloquearAsistente(_OperacionEquipo):
    def ejecutar(
        self, sesion: SesionActiva, asistente_id: UUID, motivo: str | None
    ) -> MiembroEquipo:
        self._exigir_gerente(sesion)
        with self._unidad() as uow:
            ahora = self._reloj()
            gerente = self._gerente(uow, sesion)
            asistente = self._asistente(uow, gerente, asistente_id)
            if asistente.bloqueada:
                raise CuentaYaBloqueada()
            asistente.bloquear_por_gerente(ahora)
            uow.usuarios.guardar(asistente)
            # Deja de trabajar al momento: sus sesiones abiertas se cierran.
            cerradas = uow.sesiones.revocar_de_usuario(asistente.id, ahora, "bloqueo_gerente")
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_BLOQUEADA,
                    actor_id=gerente.id,
                    cuenta_id=asistente.id,
                    motivo=motivo,
                    detalle={"causa": "gerente", "sesiones_cerradas": cerradas},
                )
            )
            return self._miembro(uow, asistente)


class DesbloquearAsistente(_OperacionEquipo):
    def ejecutar(
        self, sesion: SesionActiva, asistente_id: UUID, motivo: str | None
    ) -> MiembroEquipo:
        self._exigir_gerente(sesion, limitar=False)
        exigir_cupo(self._limitador, (self._limites.desbloqueo, str(sesion.usuario.id)))
        with self._unidad() as uow:
            gerente = self._gerente(uow, sesion)
            asistente = self._asistente(uow, gerente, asistente_id)
            if not asistente.bloqueada:
                raise CuentaNoBloqueada()
            intentos, causa = asistente.intentos_fallidos, asistente.causa_bloqueo
            asistente.desbloquear()
            uow.usuarios.guardar(asistente)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_DESBLOQUEADA,
                    actor_id=gerente.id,
                    cuenta_id=asistente.id,
                    motivo=motivo,
                    detalle={
                        "intentos_fallidos": intentos,
                        "causa": causa.value if causa else None,
                    },
                )
            )
            return self._miembro(uow, asistente)


class EliminarAsistente(_OperacionEquipo):
    def ejecutar(self, sesion: SesionActiva, asistente_id: UUID, motivo: str | None) -> None:
        self._exigir_gerente(sesion)
        with self._unidad() as uow:
            ahora = self._reloj()
            gerente = self._gerente(uow, sesion)
            asistente = self._asistente(uow, gerente, asistente_id)
            asistente.eliminar(ahora)
            uow.usuarios.guardar(asistente)
            cerradas = uow.sesiones.revocar_de_usuario(asistente.id, ahora, "cuenta_eliminada")
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_ELIMINADA,
                    actor_id=gerente.id,
                    cuenta_id=asistente.id,
                    motivo=motivo,
                    detalle={"sesiones_cerradas": cerradas},
                )
            )


class RecuperarAsistente(_OperacionEquipo):
    def ejecutar(self, sesion: SesionActiva, asistente_id: UUID) -> CredencialesEntregadas:
        self._exigir_gerente(sesion)
        with self._unidad() as uow:
            ahora = self._reloj()
            gerente = self._gerente(uow, sesion)
            asistente = self._asistente(uow, gerente, asistente_id, eliminada=True)
            if not asistente.eliminada:
                raise CuentaNoEliminada()
            ficha = uow.usuarios.ficha(asistente.id)
            assert ficha is not None
            # Mientras estuvo eliminada pudo crearse otra cuenta con su documento.
            otras = uow.usuarios.por_documento(
                ficha.datos.tipo_documento, ficha.datos.numero_documento
            )
            if any(not cuenta.eliminada for cuenta in otras):
                raise DatosDuplicados(campos={"numero_documento": DOCUMENTO_DE_OTRA_CUENTA})
            contrasena = generar_contrasena_temporal(asistente.nombre_usuario)
            asistente.recuperar(self._contrasenas.generar_hash(contrasena), ahora)
            uow.usuarios.guardar(asistente)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_RECUPERADA, actor_id=gerente.id, cuenta_id=asistente.id
                )
            )
            return CredencialesEntregadas(MiembroEquipo(asistente, ficha), contrasena)
