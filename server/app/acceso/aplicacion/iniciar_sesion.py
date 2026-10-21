from dataclasses import dataclass
from datetime import datetime, timedelta

from app.acceso.aplicacion.limites import LimitesAcceso, exigir_cupo
from app.acceso.dominio.errores import CredencialesIncorrectas, CuentaBloqueada, ErrorAcceso
from app.acceso.dominio.modelos import (
    Accion,
    EventoAuditoria,
    Usuario,
    normalizar_nombre_usuario,
    nueva_sesion,
)
from app.acceso.dominio.puertos import (
    FabricaUnidadDeTrabajo,
    LimitadorSolicitudes,
    ProtectorContrasenas,
    Reloj,
)


@dataclass(frozen=True)
class SesionIniciada:
    token: str
    expira_en: datetime
    usuario: Usuario
    primer_ingreso: bool


class IniciarSesion:
    def __init__(
        self,
        unidad: FabricaUnidadDeTrabajo,
        contrasenas: ProtectorContrasenas,
        limitador: LimitadorSolicitudes,
        limites: LimitesAcceso,
        reloj: Reloj,
        duracion_sesion: timedelta,
    ) -> None:
        self._unidad = unidad
        self._contrasenas = contrasenas
        self._limitador = limitador
        self._limites = limites
        self._reloj = reloj
        self._duracion = duracion_sesion

    def ejecutar(self, nombre_usuario: str, contrasena: str, origen: str) -> SesionIniciada:
        nombre = normalizar_nombre_usuario(nombre_usuario)
        # La frecuencia se limita antes de tocar la base: por origen frena a un atacante que
        # prueba muchos usuarios y por usuario frena ataques repartidos entre muchas IP.
        exigir_cupo(
            self._limitador,
            (self._limites.ingreso_por_origen, origen),
            (self._limites.ingreso_por_usuario, nombre),
        )
        fallo: ErrorAcceso | None = None
        resultado: SesionIniciada | None = None
        with self._unidad() as uow:
            ahora = self._reloj()
            usuario = uow.usuarios.por_nombre_usuario(nombre, bloquear=True)
            if usuario is None:
                self._contrasenas.simular_verificacion(contrasena)
                # No se guarda el usuario escrito: podría ser una contraseña tecleada por error.
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.INGRESO_FALLIDO, detalle={"causa": "usuario_desconocido"}
                    )
                )
                fallo = CredencialesIncorrectas()
            elif usuario.bloqueada:
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.INGRESO_RECHAZADO,
                        cuenta_id=usuario.id,
                        detalle={"causa": "cuenta_bloqueada"},
                    )
                )
                fallo = CuentaBloqueada()
            elif not self._contrasenas.verificar(usuario.contrasena_hash, contrasena):
                se_bloqueo = usuario.registrar_intento_fallido(ahora)
                uow.usuarios.guardar(usuario)
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.INGRESO_FALLIDO,
                        cuenta_id=usuario.id,
                        detalle={"intentos_fallidos": usuario.intentos_fallidos},
                    )
                )
                if se_bloqueo:
                    # Las sesiones abiertas también se cierran: el bloqueo puede responder a un
                    # ataque en curso.
                    uow.sesiones.revocar_de_usuario(usuario.id, ahora, "cuenta_bloqueada")
                    uow.auditoria.registrar(
                        EventoAuditoria(
                            Accion.CUENTA_BLOQUEADA,
                            cuenta_id=usuario.id,
                            motivo="Intentos fallidos de inicio de sesión",
                        )
                    )
                    fallo = CuentaBloqueada()
                else:
                    fallo = CredencialesIncorrectas()
            else:
                primer_ingreso = usuario.primer_ingreso
                usuario.registrar_ingreso(ahora)
                if self._contrasenas.necesita_rehash(usuario.contrasena_hash):
                    usuario.contrasena_hash = self._contrasenas.generar_hash(contrasena)
                uow.usuarios.guardar(usuario)
                token, sesion = nueva_sesion(usuario.id, ahora, self._duracion)
                uow.sesiones.agregar(sesion)
                uow.auditoria.registrar(
                    EventoAuditoria(
                        Accion.INGRESO_EXITOSO, actor_id=usuario.id, cuenta_id=usuario.id
                    )
                )
                resultado = SesionIniciada(token, sesion.expira_en, usuario, primer_ingreso)
        # El error se lanza después de confirmar: el contador y la auditoría deben quedar guardados.
        if fallo is not None:
            raise fallo
        assert resultado is not None
        return resultado
