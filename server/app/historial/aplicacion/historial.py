"""Casos de uso del historial: consultarlo con filtros, página a página, y exportarlo.

Consultar: todo el espacio, el gerente y sus asistentes. Exportar: solo el gerente, con el detalle
de cada cuota y sin datos personales cifrados (ni titular ni código de pago; quien registró o pagó
va con su nombre de usuario).
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.dominio.errores import SinPermiso
from app.acceso.dominio.modelos import Rol
from app.acceso.dominio.puertos import Reloj
from app.categorias.aplicacion.categorias import espacio_de
from app.deudas.dominio.modelos import LugarPago
from app.historial.dominio.errores import FiltroInvalido
from app.historial.dominio.modelos import (
    DIAS_POR_DEFECTO,
    LARGO_BUSQUEDA,
    RANGO_MAXIMO_DIAS,
    DeudaHistorial,
    EstadoFiltro,
    Filtros,
    Posicion,
)
from app.historial.dominio.puertos import FabricaUnidadHistorial, UnidadHistorial

LIMITE_PAGINA = 25
LIMITE_MAXIMO = 100
# La exportación lee de a bloques y se detiene aquí: un rango de un año cabe de sobra.
DEUDAS_EXPORTACION = 5000
BLOQUE_EXPORTACION = 200


@dataclass(frozen=True)
class ConsultaHistorial:
    """Lo que pide la persona; sin fechas, los últimos 90 días."""

    desde: date | None = None
    hasta: date | None = None
    estado: EstadoFiltro | None = None
    categoria_id: UUID | None = None
    registrada_por: UUID | None = None
    pagado_por: UUID | None = None
    lugar_pago: LugarPago | None = None
    texto: str | None = None
    mios: bool = False


@dataclass(frozen=True)
class PaginaHistorial:
    hoy: date
    filtros: Filtros
    deudas: list[DeudaHistorial]
    # El nombre de cada cuenta que aparece en la página.
    nombres: dict[UUID, str]
    siguiente: Posicion | None
    gerente: bool


@dataclass(frozen=True)
class Exportacion:
    filtros: Filtros
    deudas: list[DeudaHistorial]
    usuarios: dict[UUID, str]
    categorias: dict[UUID, str]
    # Se cortó en DEUDAS_EXPORTACION: conviene acotar el rango.
    incompleta: bool


def _nombres(uow: UnidadHistorial, deudas: list[DeudaHistorial]) -> dict[UUID, str]:
    nombres: dict[UUID, str] = {}
    for usuario_id in set().union(*(d.actores() for d in deudas)):
        ficha = uow.cuentas.ficha(usuario_id)
        nombres[usuario_id] = (
            f"{ficha.datos.nombres} {ficha.datos.apellidos}" if ficha else "Cuenta eliminada"
        )
    return nombres


class _OperacionHistorial:
    def __init__(self, unidad: FabricaUnidadHistorial, reloj: Reloj, zona: ZoneInfo) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._zona = zona

    def _hoy(self) -> date:
        return self._reloj().astimezone(self._zona).date()

    def _filtros(self, sesion: SesionActiva, consulta: ConsultaHistorial) -> Filtros:
        hasta = consulta.hasta or self._hoy()
        desde = consulta.desde or hasta - timedelta(days=DIAS_POR_DEFECTO - 1)
        if desde > hasta:
            raise FiltroInvalido(campos={"desde": "La fecha inicial va antes de la final."})
        if (hasta - desde).days + 1 > RANGO_MAXIMO_DIAS:
            mensaje = f"Elige un rango de hasta {RANGO_MAXIMO_DIAS} días."
            raise FiltroInvalido(mensaje, campos={"desde": mensaje})
        texto = " ".join((consulta.texto or "").split()) or None
        if texto and len(texto) > LARGO_BUSQUEDA:
            mensaje = f"Busca con {LARGO_BUSQUEDA} caracteres como máximo."
            raise FiltroInvalido(mensaje, campos={"q": mensaje})
        return Filtros(
            desde=desde,
            hasta=hasta,
            estado=consulta.estado,
            categoria_id=consulta.categoria_id,
            registrada_por=consulta.registrada_por,
            pagado_por=consulta.pagado_por,
            lugar_pago=consulta.lugar_pago,
            texto=texto,
            de_la_cuenta=sesion.usuario.id if consulta.mios else None,
        )

    def _rango(self, filtros: Filtros) -> tuple[datetime, datetime]:
        """Los días del espacio, de la medianoche de `desde` a la del día siguiente a `hasta`."""
        inicio = datetime.combine(filtros.desde, time(), self._zona)
        fin = datetime.combine(filtros.hasta + timedelta(days=1), time(), self._zona)
        return inicio, fin


class ConsultarHistorial(_OperacionHistorial):
    def ejecutar(
        self,
        sesion: SesionActiva,
        consulta: ConsultaHistorial,
        despues: Posicion | None = None,
        limite: int = LIMITE_PAGINA,
    ) -> PaginaHistorial:
        filtros = self._filtros(sesion, consulta)
        inicio, fin = self._rango(filtros)
        limite = max(1, min(limite, LIMITE_MAXIMO))
        with self._unidad() as uow:
            # Una de más dice si hay otra página.
            deudas = uow.historial.buscar(
                espacio_de(sesion), filtros, inicio, fin, despues, limite + 1
            )
            pagina = deudas[:limite]
            nombres = _nombres(uow, pagina)
        return PaginaHistorial(
            self._hoy(),
            filtros,
            pagina,
            nombres,
            pagina[-1].posicion if len(deudas) > limite else None,
            sesion.usuario.rol is Rol.GERENTE,
        )


class ExportarHistorial(_OperacionHistorial):
    def ejecutar(self, sesion: SesionActiva, consulta: ConsultaHistorial) -> Exportacion:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        filtros = self._filtros(sesion, replace(consulta, mios=False))
        inicio, fin = self._rango(filtros)
        deudas: list[DeudaHistorial] = []
        despues: Posicion | None = None
        with self._unidad() as uow:
            # Hasta pasar el tope: así se sabe si quedó algo fuera.
            while len(deudas) <= DEUDAS_EXPORTACION:
                bloque = uow.historial.buscar(
                    sesion.usuario.id, filtros, inicio, fin, despues, BLOQUE_EXPORTACION
                )
                deudas.extend(bloque)
                if len(bloque) < BLOQUE_EXPORTACION:
                    break
                despues = bloque[-1].posicion
            incompleta = len(deudas) > DEUDAS_EXPORTACION
            deudas = deudas[:DEUDAS_EXPORTACION]
            usuarios = uow.historial.usuarios(set().union(*(d.actores() for d in deudas)))
            categorias = uow.historial.categorias(sesion.usuario.id)
        return Exportacion(filtros, deudas, usuarios, categorias, incompleta)
