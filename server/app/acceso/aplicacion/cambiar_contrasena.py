from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.aplicacion.pasos import pasos_de
from app.acceso.dominio import politica_contrasena
from app.acceso.dominio.errores import (
    ContrasenaActualIncorrecta,
    ContrasenaInsegura,
    ContrasenaRepetida,
    ErrorAcceso,
    NoAutenticado,
)
from app.acceso.dominio.modelos import Accion, EventoAuditoria
from app.acceso.dominio.puertos import (
    FabricaUnidadDeTrabajo,
    LimitadorSolicitudes,
    ProtectorContrasenas,
    Reloj,
)


class CambiarContrasena:
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

    def ejecutar(self, sesion: SesionActiva, actual: str, nueva: str) -> SesionActiva:
        """Devuelve la sesión actualizada: tras la contraseña inicial sigue la aceptación."""
        exigir_cupo(self._limitador, (self._limites.cambio_contrasena, str(sesion.usuario.id)))
        fallo: ErrorAcceso | None = None
        with self._unidad() as uow:
            ahora = self._reloj()
            usuario = uow.usuarios.por_id(sesion.usuario.id, bloquear=True)
            if usuario is None or usuario.bloqueada or usuario.eliminada:
                raise NoAutenticado()
            incumplidos = politica_contrasena.evaluar(nueva, nombre_usuario=usuario.nombre_usuario)
            if not self._contrasenas.verificar(usuario.contrasena_hash, actual):
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.CAMBIO_CONTRASENA_FALLIDO,
                        actor_id=usuario.id,
                        cuenta_id=usuario.id,
                        detalle={"causa": "contrasena_actual_incorrecta"},
                    )
                )
                fallo = ContrasenaActualIncorrecta()
            elif incumplidos:
                fallo = ContrasenaInsegura(incumplidos)
            elif self._contrasenas.verificar(usuario.contrasena_hash, nueva):
                fallo = ContrasenaRepetida()
            else:
                era_inicial = usuario.debe_cambiar_contrasena
                usuario.cambiar_contrasena(self._contrasenas.generar_hash(nueva), ahora)
                uow.usuarios.guardar(usuario)
                # Las demás sesiones abiertas con la contraseña anterior dejan de valer.
                cerradas = uow.sesiones.revocar_de_usuario(
                    usuario.id, ahora, "cambio_contrasena", excepto=sesion.sesion_id
                )
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.CONTRASENA_CAMBIADA,
                        actor_id=usuario.id,
                        cuenta_id=usuario.id,
                        detalle={"era_inicial": era_inicial, "sesiones_cerradas": cerradas},
                    )
                )
                pasos = pasos_de(uow, usuario, ahora)
        if fallo is not None:
            raise fallo
        return SesionActiva(sesion.sesion_id, usuario, pasos)
