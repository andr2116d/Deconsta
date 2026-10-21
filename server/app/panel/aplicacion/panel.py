"""Consulta del panel de inicio: el gerente ve su resumen; la asistente, su jornada."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.dominio.modelos import Rol
from app.acceso.dominio.puertos import Reloj
from app.categorias.aplicacion.categorias import espacio_de
from app.panel.dominio.modelos import PanelAsistente, PanelGerente
from app.panel.dominio.puertos import UnidadPanel

PROXIMAS = 4


@dataclass(frozen=True)
class Panel:
    hoy: date
    gerente: PanelGerente | None
    asistente: PanelAsistente | None
    # El nombre de cada cuenta que aparece en el panel.
    nombres: dict[UUID, str]


class ConsultarPanel:
    def __init__(self, unidad: Callable[[], UnidadPanel], reloj: Reloj, zona: ZoneInfo) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._zona = zona

    def ejecutar(self, sesion: SesionActiva) -> Panel:
        hoy = self._reloj().astimezone(self._zona).date()
        usuario = sesion.usuario
        gerente_id = espacio_de(sesion)
        with self._unidad() as uow:
            panel = uow.panel
            if usuario.rol is Rol.GERENTE:
                por_pagar, cuotas, vencidas = panel.por_pagar(gerente_id, hoy)
                pagado, pagos = panel.pagado_entre(gerente_id, hoy.replace(day=1), hoy)
                pendientes = sorted(
                    panel.pendientes(gerente_id), key=lambda p: (p.vence_el, p.desde)
                )
                proximas = panel.proximas(gerente_id, PROXIMAS)
                resumen = PanelGerente(
                    por_pagar, cuotas, vencidas, pagado, pagos, pendientes, proximas
                )
                ids = {p.por for p in pendientes} | {c.pedido_a for c in proximas if c.pedido_a}
                jornada = None
            else:
                _, cuotas, _ = panel.por_pagar(gerente_id, hoy)
                pedidas = panel.pedidas_a(usuario.id)
                siguiente = (
                    pedidas[0] if pedidas else next(iter(panel.proximas(gerente_id, 1)), None)
                )
                jornada = PanelAsistente(
                    cuotas,
                    panel.devueltas(gerente_id),
                    panel.en_espera_de(usuario.id),
                    siguiente,
                    panel.limite(gerente_id),
                )
                ids = {gerente_id}
                resumen = None
            nombres = {}
            for cuenta_id in ids:
                ficha = uow.cuentas.ficha(cuenta_id)
                nombres[cuenta_id] = (
                    f"{ficha.datos.nombres} {ficha.datos.apellidos}"
                    if ficha
                    else "Cuenta eliminada"
                )
        return Panel(hoy, resumen, jornada, nombres)
