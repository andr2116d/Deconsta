from datetime import datetime

from app.acceso.dominio.incorporacion import PasoPendiente, pasos_pendientes
from app.acceso.dominio.modelos import Usuario
from app.acceso.dominio.puertos import UnidadDeTrabajo


def pasos_de(uow: UnidadDeTrabajo, usuario: Usuario, ahora: datetime) -> tuple[PasoPendiente, ...]:
    """Pasos del primer ingreso que le faltan a la cuenta, según el estado guardado."""
    return pasos_pendientes(
        uow.documentos.hay_sin_aceptar(usuario.id, ahora), usuario.debe_confirmar_datos
    )
