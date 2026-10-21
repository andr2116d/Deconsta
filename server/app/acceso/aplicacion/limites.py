from dataclasses import dataclass

from app.acceso.dominio.errores import DemasiadasSolicitudes
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite


@dataclass(frozen=True)
class LimitesAcceso:
    ingreso_por_origen: Limite
    ingreso_por_usuario: Limite
    cambio_contrasena: Limite
    desbloqueo: Limite
    actualizacion_cuenta: Limite
    gestion_equipo: Limite


def exigir_cupo(limitador: LimitadorSolicitudes, *consumos: tuple[Limite, str]) -> None:
    """Consume todos los límites indicados y rechaza si alguno se superó."""
    cupos = [limitador.consumir(limite, identificador) for limite, identificador in consumos]
    esperas = [cupo.reintentar_en for cupo in cupos if not cupo.permitido]
    if esperas:
        raise DemasiadasSolicitudes(max(esperas))
