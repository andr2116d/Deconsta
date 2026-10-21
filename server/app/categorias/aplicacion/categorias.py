"""Casos de uso de las categorías del espacio.

El espacio es el del gerente: él crea, edita, archiva y reactiva sus categorías; sus asistentes solo
consultan las activas. El espacio sale siempre de la sesión, nunca de lo que envía el cliente, y una
categoría de otro espacio responde igual que una inexistente. Cada escritura toma la fila del
gerente con FOR UPDATE, así el tope de categorías y la unicidad del nombre se comprueban sin
carreras, y deja constancia en la auditoría.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.limites import exigir_cupo
from app.acceso.dominio.errores import NoAutenticado, SinPermiso
from app.acceso.dominio.modelos import Accion, EventoAuditoria, Rol
from app.acceso.dominio.puertos import LimitadorSolicitudes, Limite, Reloj
from app.categorias.dominio.errores import (
    CategoriaDuplicada,
    CategoriaNoEncontrada,
    LimiteCategorias,
)
from app.categorias.dominio.modelos import (
    MAXIMO_CATEGORIAS_ACTIVAS,
    Categoria,
    Color,
    DatosCategoria,
    Icono,
)
from app.categorias.dominio.puertos import FabricaUnidadCategorias, UnidadCategorias

COLORES = list(Color)


@dataclass(frozen=True)
class NuevaCategoria:
    nombre: str
    descripcion: str | None = None
    # Sin color, se toma el siguiente de la paleta; sin ícono, una etiqueta.
    color: str | None = None
    icono: str | None = None


def espacio_de(sesion: SesionActiva) -> UUID:
    """El gerente es dueño de su espacio; una asistente trabaja en el de su gerente."""
    usuario = sesion.usuario
    if usuario.rol is Rol.GERENTE:
        return usuario.id
    assert usuario.gerente_id is not None
    return usuario.gerente_id


class _OperacionCategorias:
    def __init__(
        self,
        unidad: FabricaUnidadCategorias,
        limitador: LimitadorSolicitudes,
        limite: Limite,
        reloj: Reloj,
    ) -> None:
        self._unidad = unidad
        self._limitador = limitador
        self._limite = limite
        self._reloj = reloj

    def _exigir_gerente(self, sesion: SesionActiva) -> UUID:
        if sesion.usuario.rol is not Rol.GERENTE:
            raise SinPermiso()
        exigir_cupo(self._limitador, (self._limite, str(sesion.usuario.id)))
        return sesion.usuario.id

    @staticmethod
    def _bloquear(uow: UnidadCategorias, gerente_id: UUID) -> None:
        if not uow.categorias.bloquear_espacio(gerente_id):
            raise NoAutenticado()

    @staticmethod
    def _categoria(uow: UnidadCategorias, gerente_id: UUID, categoria_id: UUID) -> Categoria:
        categoria = uow.categorias.por_id(gerente_id, categoria_id)
        if categoria is None:
            raise CategoriaNoEncontrada()
        return categoria

    @staticmethod
    def _exigir_nombre_libre(
        uow: UnidadCategorias, gerente_id: UUID, datos: DatosCategoria, propia: UUID | None = None
    ) -> None:
        existente = uow.categorias.por_clave(gerente_id, datos.clave)
        if existente is not None and existente.id != propia:
            raise CategoriaDuplicada(existente.nombre, existente.id, existente.archivada)

    @staticmethod
    def _exigir_cupo_activas(uow: UnidadCategorias, gerente_id: UUID) -> None:
        if uow.categorias.contar_activas(gerente_id) >= MAXIMO_CATEGORIAS_ACTIVAS:
            raise LimiteCategorias(MAXIMO_CATEGORIAS_ACTIVAS)

    @staticmethod
    def _auditar(
        uow: UnidadCategorias,
        accion: Accion,
        sesion: SesionActiva,
        categoria: Categoria,
        motivo: str | None = None,
        **detalle: object,
    ) -> None:
        uow.auditoria.registrar(
            EventoAuditoria(
                accion,
                actor_id=sesion.usuario.id,
                motivo=motivo,
                detalle={"categoria_id": str(categoria.id), "nombre": categoria.nombre, **detalle},
            )
        )


class ListarCategorias(_OperacionCategorias):
    def ejecutar(
        self, sesion: SesionActiva, *, incluir_archivadas: bool = False
    ) -> list[Categoria]:
        # Las archivadas solo le sirven al gerente para reactivarlas.
        archivadas = incluir_archivadas and sesion.usuario.rol is Rol.GERENTE
        with self._unidad() as uow:
            return uow.categorias.del_espacio(espacio_de(sesion), incluir_archivadas=archivadas)


class CrearCategoria(_OperacionCategorias):
    def ejecutar(self, sesion: SesionActiva, nueva: NuevaCategoria) -> Categoria:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            datos = DatosCategoria.crear(
                nombre=nueva.nombre,
                descripcion=nueva.descripcion,
                color=nueva.color or COLORES[uow.categorias.contar(gerente_id) % len(COLORES)],
                icono=nueva.icono or Icono.ETIQUETA,
            )
            self._exigir_nombre_libre(uow, gerente_id, datos)
            self._exigir_cupo_activas(uow, gerente_id)
            ahora = self._reloj()
            categoria = Categoria(
                id=uuid4(),
                gerente_id=gerente_id,
                nombre=datos.nombre,
                descripcion=datos.descripcion,
                color=datos.color,
                icono=datos.icono,
                creado_por=sesion.usuario.id,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            uow.categorias.agregar(categoria)
            self._auditar(uow, Accion.CATEGORIA_CREADA, sesion, categoria)
            return categoria


class EditarCategoria(_OperacionCategorias):
    def ejecutar(
        self, sesion: SesionActiva, categoria_id: UUID, nueva: NuevaCategoria
    ) -> Categoria:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            categoria = self._categoria(uow, gerente_id, categoria_id)
            categoria.exigir_activa()
            # Sin color o sin ícono, se conservan los actuales.
            datos = DatosCategoria.crear(
                nombre=nueva.nombre,
                descripcion=nueva.descripcion,
                color=nueva.color or categoria.color,
                icono=nueva.icono or categoria.icono,
            )
            self._exigir_nombre_libre(uow, gerente_id, datos, propia=categoria.id)
            cambios = categoria.editar(datos, self._reloj())
            uow.categorias.guardar(categoria)
            self._auditar(uow, Accion.CATEGORIA_EDITADA, sesion, categoria, cambios=cambios)
            return categoria


class ArchivarCategoria(_OperacionCategorias):
    def ejecutar(self, sesion: SesionActiva, categoria_id: UUID, motivo: str | None) -> Categoria:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            categoria = self._categoria(uow, gerente_id, categoria_id)
            categoria.archivar(self._reloj())
            uow.categorias.guardar(categoria)
            self._auditar(uow, Accion.CATEGORIA_ARCHIVADA, sesion, categoria, motivo)
            return categoria


class ReactivarCategoria(_OperacionCategorias):
    def ejecutar(self, sesion: SesionActiva, categoria_id: UUID) -> Categoria:
        gerente_id = self._exigir_gerente(sesion)
        with self._unidad() as uow:
            self._bloquear(uow, gerente_id)
            categoria = self._categoria(uow, gerente_id, categoria_id)
            if categoria.archivada:
                self._exigir_cupo_activas(uow, gerente_id)
            categoria.reactivar(self._reloj())
            uow.categorias.guardar(categoria)
            self._auditar(uow, Accion.CATEGORIA_REACTIVADA, sesion, categoria)
            return categoria
