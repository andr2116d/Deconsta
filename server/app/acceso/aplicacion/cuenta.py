"""Casos de uso de «Mi cuenta»: la persona consulta y actualiza sus propios datos.

Cada operación trabaja solo sobre la cuenta de la sesión: el cliente nunca indica qué cuenta
cambiar. La fila del usuario se toma con FOR UPDATE, así que dos envíos simultáneos de la misma
cuenta se atienden uno tras otro y el límite mensual de cambios de usuario no se puede rebasar.
"""

from dataclasses import dataclass
from datetime import datetime, tzinfo

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.dominio.cuenta import (
    CupoNombreUsuario,
    FichaPersonal,
    periodo_mensual,
    revisar_cambios,
)
from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import (
    ContrasenaActualIncorrecta,
    ContrasenaRequerida,
    DatosInvalidos,
    ErrorAcceso,
    LimiteCambiosNombreUsuario,
    NoAutenticado,
    SinCambios,
)
from app.acceso.dominio.modelos import (
    REGLA_NOMBRE_USUARIO,
    Accion,
    EventoAuditoria,
    Usuario,
    nombre_usuario_valido,
    normalizar_nombre_usuario,
)
from app.acceso.dominio.puertos import (
    FabricaUnidadDeTrabajo,
    LimitadorSolicitudes,
    ProtectorContrasenas,
    Reloj,
    UnidadDeTrabajo,
)


@dataclass(frozen=True)
class CuentaPropia:
    usuario: Usuario
    ficha: FichaPersonal
    cambios_nombre_usuario: CupoNombreUsuario


def _usuario_vigente(uow: UnidadDeTrabajo, sesion: SesionActiva) -> Usuario:
    usuario = uow.usuarios.por_id(sesion.usuario.id, bloquear=True)
    if usuario is None or usuario.bloqueada or usuario.eliminada:
        raise NoAutenticado()
    return usuario


def _ficha(uow: UnidadDeTrabajo, usuario: Usuario) -> FichaPersonal:
    ficha = uow.usuarios.ficha(usuario.id)
    if ficha is None:
        raise NoAutenticado()
    return ficha


def _cupo(
    uow: UnidadDeTrabajo, usuario: Usuario, ahora: datetime, zona: tzinfo
) -> CupoNombreUsuario:
    inicio, siguiente = periodo_mensual(ahora, zona)
    return CupoNombreUsuario(
        uow.usuarios.cambios_nombre_usuario_desde(usuario.id, inicio), siguiente
    )


class _OperacionCuenta:
    def __init__(
        self,
        unidad: FabricaUnidadDeTrabajo,
        contrasenas: ProtectorContrasenas,
        limitador: LimitadorSolicitudes,
        limites: LimitesAcceso,
        reloj: Reloj,
        zona: tzinfo,
    ) -> None:
        self._unidad = unidad
        self._contrasenas = contrasenas
        self._limitador = limitador
        self._limites = limites
        self._reloj = reloj
        self._zona = zona

    def _exigir_cupo(self, sesion: SesionActiva) -> None:
        # También frena a quien prueba contraseñas a través de la confirmación.
        exigir_cupo(self._limitador, (self._limites.actualizacion_cuenta, str(sesion.usuario.id)))

    def _confirmar(
        self, uow: UnidadDeTrabajo, usuario: Usuario, contrasena: str | None, operacion: str
    ) -> ErrorAcceso | None:
        """Comprueba la contraseña actual. El fallo se devuelve para lanzarlo tras confirmar la
        transacción: el intento debe quedar en la auditoría."""
        if not contrasena:
            raise ContrasenaRequerida()
        if self._contrasenas.verificar(usuario.contrasena_hash, contrasena):
            return None
        uow.auditoria.registrar(
            EventoAuditoria(
                Accion.CONFIRMACION_CONTRASENA_FALLIDA,
                actor_id=usuario.id,
                cuenta_id=usuario.id,
                detalle={"operacion": operacion},
            )
        )
        return ContrasenaActualIncorrecta()


class ConsultarCuenta(_OperacionCuenta):
    def ejecutar(self, sesion: SesionActiva) -> CuentaPropia:
        with self._unidad() as uow:
            usuario = uow.usuarios.por_id(sesion.usuario.id, bloquear=False)
            if usuario is None or usuario.bloqueada or usuario.eliminada:
                raise NoAutenticado()
            return CuentaPropia(
                usuario, _ficha(uow, usuario), _cupo(uow, usuario, self._reloj(), self._zona)
            )


class ActualizarDatosPersonales(_OperacionCuenta):
    def ejecutar(
        self,
        sesion: SesionActiva,
        nuevos: DatosPersonales,
        *,
        contrasena_actual: str | None,
        confirmar_cambio_documento: bool,
    ) -> CuentaPropia:
        self._exigir_cupo(sesion)
        with self._unidad() as uow:
            ahora = self._reloj()
            usuario = _usuario_vigente(uow, sesion)
            actual = _ficha(uow, usuario)
            cambios = revisar_cambios(
                actual.datos,
                nuevos,
                rol=usuario.rol,
                confirmar_documento=confirmar_cambio_documento,
            )
            fallo = None
            if cambios.requiere_contrasena:
                fallo = self._confirmar(uow, usuario, contrasena_actual, "datos_personales")
            if fallo is None:
                uow.usuarios.actualizar_datos(usuario.id, nuevos)
                usuario.nombres = nuevos.nombres
                # Solo los nombres de los campos: los valores son datos personales.
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.DATOS_PERSONALES_ACTUALIZADOS,
                        actor_id=usuario.id,
                        cuenta_id=usuario.id,
                        detalle={"campos": list(cambios.campos)},
                    )
                )
                if cambios.cambia_documento:
                    uow.auditoria.registrar(
                        EventoAuditoria(
                            Accion.DOCUMENTO_CAMBIADO,
                            actor_id=usuario.id,
                            cuenta_id=usuario.id,
                            motivo="Cambio de DNI a carné de extranjería confirmado por la cuenta",
                            detalle={
                                "de": actual.datos.tipo_documento.value,
                                "a": nuevos.tipo_documento.value,
                            },
                        )
                    )
                cuenta = CuentaPropia(
                    usuario,
                    FichaPersonal(nuevos, actual.cargo),
                    _cupo(uow, usuario, ahora, self._zona),
                )
        if fallo is not None:
            raise fallo
        return cuenta


class CambiarNombreUsuario(_OperacionCuenta):
    def ejecutar(self, sesion: SesionActiva, nuevo: str, contrasena_actual: str) -> CuentaPropia:
        nombre = normalizar_nombre_usuario(nuevo)
        if not nombre_usuario_valido(nombre):
            raise DatosInvalidos(campos={"nombre_usuario": REGLA_NOMBRE_USUARIO})
        self._exigir_cupo(sesion)
        with self._unidad() as uow:
            ahora = self._reloj()
            usuario = _usuario_vigente(uow, sesion)
            if nombre == usuario.nombre_usuario:
                raise SinCambios("Ese ya es tu usuario.")
            # La contraseña se comprueba antes que la disponibilidad: sin ella no se revela qué
            # usuarios existen.
            fallo = self._confirmar(uow, usuario, contrasena_actual, "nombre_usuario")
            if fallo is None:
                cupo = _cupo(uow, usuario, ahora, self._zona)
                if cupo.restantes == 0:
                    raise LimiteCambiosNombreUsuario(cupo.maximo, cupo.renueva_en)
                anterior = usuario.nombre_usuario
                uow.usuarios.cambiar_nombre_usuario(usuario.id, anterior, nombre, ahora)
                usuario.nombre_usuario = nombre
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.NOMBRE_USUARIO_CAMBIADO,
                        actor_id=usuario.id,
                        cuenta_id=usuario.id,
                        detalle={"anterior": anterior, "nuevo": nombre},
                    )
                )
                cuenta = CuentaPropia(
                    usuario,
                    _ficha(uow, usuario),
                    CupoNombreUsuario(cupo.usados + 1, cupo.renueva_en),
                )
        if fallo is not None:
            raise fallo
        return cuenta
