"""Raíz de composición: conecta los casos de uso con sus adaptadores concretos."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from redis import Redis
from sqlalchemy import Engine

from app.acceso.aplicacion.autenticar import Autenticar, CerrarSesion
from app.acceso.aplicacion.cambiar_contrasena import CambiarContrasena
from app.acceso.aplicacion.crear_cuenta import CrearCuenta
from app.acceso.aplicacion.cuenta import (
    ActualizarDatosPersonales,
    CambiarNombreUsuario,
    ConsultarCuenta,
)
from app.acceso.aplicacion.equipo import (
    BloquearAsistente,
    DesbloquearAsistente,
    EliminarAsistente,
    ListarEquipo,
    RecuperarAsistente,
    RegistrarAsistente,
    RestablecerContrasena,
)
from app.acceso.aplicacion.incorporacion import (
    AceptarDocumentos,
    ConfirmarDatos,
    ConsultarDocumentos,
)
from app.acceso.aplicacion.iniciar_sesion import IniciarSesion
from app.acceso.aplicacion.limites import LimitesAcceso
from app.acceso.dominio.puertos import Limite
from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.contrasenas import ProtectorArgon2
from app.acceso.infraestructura.limitador_redis import LimitadorRedis
from app.acceso.infraestructura.persistencia import UnidadDeTrabajoSql
from app.categorias.aplicacion.categorias import (
    ArchivarCategoria,
    CrearCategoria,
    EditarCategoria,
    ListarCategorias,
    ReactivarCategoria,
)
from app.categorias.infraestructura.persistencia import UnidadCategoriasSql
from app.core.config import Settings
from app.core.database import crear_motor
from app.deudas.aplicacion.deudas import (
    AnularDeuda,
    AutorizarDeuda,
    ConsultarCalendario,
    ConsultarDeuda,
    DarVistoBueno,
    ListarDeudas,
    RechazarDeuda,
    RegistrarDeuda,
)
from app.deudas.infraestructura.persistencia import UnidadDeudasSql
from app.documentos.aplicacion.documentos import (
    ConsultarDocumento,
    LeerContenido,
    LevantarBloqueo,
    ListarBloqueos,
    SubirDocumento,
)
from app.documentos.dominio.puertos import ColaAnalisis
from app.documentos.infraestructura.cola_celery import ColaCelery
from app.documentos.infraestructura.componentes import Componentes
from app.historial.aplicacion.historial import ConsultarHistorial, ExportarHistorial
from app.historial.infraestructura.persistencia import UnidadHistorialSql
from app.notificaciones.aplicacion.notificaciones import (
    ListarNotificaciones,
    MarcarLeida,
    MarcarTodasLeidas,
)
from app.notificaciones.dominio.puertos import SuscriptorAvisos
from app.notificaciones.infraestructura.avisos_redis import SuscriptorRedis
from app.notificaciones.infraestructura.persistencia import UnidadNotificacionesSql
from app.pagos.aplicacion.pagos import (
    AprobarMora,
    ConfirmarPago,
    ConsultarComprobante,
    ConsultarMora,
    ConsultarPago,
    DeclararMora,
    DevolverPago,
    LeerComprobante,
    LevantarBloqueoPagos,
    ListarBloqueosPagos,
    ListarMoras,
    ListarPagos,
    ListarPedidos,
    ListarPorPagar,
    PedirPago,
    RechazarMora,
    RegistrarPago,
    RetirarPedido,
    SubirComprobante,
)
from app.pagos.dominio.puertos import ColaComprobantes
from app.pagos.infraestructura.cola_celery import ColaComprobantesCelery
from app.pagos.infraestructura.persistencia import UnidadPagosSql
from app.reglas.aplicacion.reglas import (
    AgregarTitular,
    CambiarLimite,
    ConsultarReglas,
    EditarTitular,
    EvaluarDocumento,
    QuitarTitular,
)
from app.reglas.infraestructura.persistencia import UnidadReglasSql


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def limites_de(config: Settings) -> LimitesAcceso:
    return LimitesAcceso(
        ingreso_por_origen=Limite(
            "ingreso_origen",
            config.limite_ingreso_por_origen,
            config.ventana_ingreso_por_origen_segundos,
        ),
        ingreso_por_usuario=Limite(
            "ingreso_usuario",
            config.limite_ingreso_por_usuario,
            config.ventana_ingreso_por_usuario_segundos,
        ),
        cambio_contrasena=Limite(
            "cambio_contrasena",
            config.limite_cambio_contrasena,
            config.ventana_cambio_contrasena_segundos,
        ),
        desbloqueo=Limite(
            "desbloqueo", config.limite_desbloqueo, config.ventana_desbloqueo_segundos
        ),
        actualizacion_cuenta=Limite(
            "actualizacion_cuenta",
            config.limite_actualizacion_cuenta,
            config.ventana_actualizacion_cuenta_segundos,
        ),
        gestion_equipo=Limite(
            "gestion_equipo", config.limite_gestion_equipo, config.ventana_gestion_equipo_segundos
        ),
    )


@dataclass
class Contenedor:
    config: Settings
    motor: Engine
    redis: Redis
    iniciar_sesion: IniciarSesion
    autenticar: Autenticar
    cerrar_sesion: CerrarSesion
    cambiar_contrasena: CambiarContrasena
    desbloquear_asistente: DesbloquearAsistente
    crear_cuenta: CrearCuenta
    consultar_documentos: ConsultarDocumentos
    aceptar_documentos: AceptarDocumentos
    consultar_cuenta: ConsultarCuenta
    actualizar_datos_personales: ActualizarDatosPersonales
    cambiar_nombre_usuario: CambiarNombreUsuario
    confirmar_datos: ConfirmarDatos
    listar_equipo: ListarEquipo
    registrar_asistente: RegistrarAsistente
    bloquear_asistente: BloquearAsistente
    eliminar_asistente: EliminarAsistente
    recuperar_asistente: RecuperarAsistente
    restablecer_contrasena: RestablecerContrasena
    listar_categorias: ListarCategorias
    crear_categoria: CrearCategoria
    editar_categoria: EditarCategoria
    archivar_categoria: ArchivarCategoria
    reactivar_categoria: ReactivarCategoria
    consultar_reglas: ConsultarReglas
    cambiar_limite: CambiarLimite
    agregar_titular: AgregarTitular
    editar_titular: EditarTitular
    quitar_titular: QuitarTitular
    evaluar_documento: EvaluarDocumento
    componentes: Componentes
    subir_documento: SubirDocumento
    consultar_documento: ConsultarDocumento
    leer_contenido: LeerContenido
    listar_bloqueos: ListarBloqueos
    levantar_bloqueo: LevantarBloqueo
    registrar_deuda: RegistrarDeuda
    listar_deudas: ListarDeudas
    consultar_deuda: ConsultarDeuda
    consultar_calendario: ConsultarCalendario
    autorizar_deuda: AutorizarDeuda
    rechazar_deuda: RechazarDeuda
    dar_visto_bueno: DarVistoBueno
    anular_deuda: AnularDeuda
    listar_notificaciones: ListarNotificaciones
    marcar_leida: MarcarLeida
    marcar_todas_leidas: MarcarTodasLeidas
    suscriptor_avisos: SuscriptorAvisos
    listar_por_pagar: ListarPorPagar
    subir_comprobante: SubirComprobante
    consultar_comprobante: ConsultarComprobante
    leer_comprobante: LeerComprobante
    registrar_pago: RegistrarPago
    listar_pagos: ListarPagos
    listar_bloqueos_pagos: ListarBloqueosPagos
    levantar_bloqueo_pagos: LevantarBloqueoPagos
    consultar_pago: ConsultarPago
    confirmar_pago: ConfirmarPago
    devolver_pago: DevolverPago
    declarar_mora: DeclararMora
    listar_moras: ListarMoras
    consultar_mora: ConsultarMora
    aprobar_mora: AprobarMora
    rechazar_mora: RechazarMora
    pedir_pago: PedirPago
    retirar_pedido: RetirarPedido
    listar_pedidos: ListarPedidos
    consultar_historial: ConsultarHistorial
    exportar_historial: ExportarHistorial

    @classmethod
    def crear(
        cls,
        config: Settings,
        *,
        componentes: Componentes | None = None,
        cola: ColaAnalisis | None = None,
        cola_comprobantes: ColaComprobantes | None = None,
    ) -> "Contenedor":
        """`componentes` y las colas reemplazan los adaptadores de los documentos y de los
        comprobantes (las pruebas los cambian por unos en memoria)."""
        motor = crear_motor(config.database_url)
        cifrador = CifradorDatos(config.clave_cifrado, config.clave_huella)
        redis = Redis.from_url(config.redis_url, socket_timeout=2, socket_connect_timeout=2)
        componentes = componentes or Componentes.crear(config, motor, redis)
        if cola is None or cola_comprobantes is None:
            from app.workers.celery_app import celery_app

            cola = cola or ColaCelery(celery_app)
            cola_comprobantes = cola_comprobantes or ColaComprobantesCelery(celery_app)
        limitador = LimitadorRedis(redis, cifrador)
        contrasenas = ProtectorArgon2()
        limites = limites_de(config)
        reloj = ahora_utc
        # Zona del negocio: define, por ejemplo, cuándo empieza el mes para los límites mensuales.
        zona = ZoneInfo(config.timezone)

        def unidad() -> UnidadDeTrabajoSql:
            return UnidadDeTrabajoSql(motor, cifrador)

        equipo = (unidad, contrasenas, limitador, limites, reloj)
        categorias = (
            lambda: UnidadCategoriasSql(motor),
            limitador,
            Limite(
                "gestion_categorias",
                config.limite_gestion_categorias,
                config.ventana_gestion_categorias_segundos,
            ),
            reloj,
        )
        reglas = (
            lambda: UnidadReglasSql(motor, cifrador),
            limitador,
            Limite(
                "gestion_reglas",
                config.limite_gestion_reglas,
                config.ventana_gestion_reglas_segundos,
            ),
            reloj,
        )

        documentos = (componentes.unidad, reloj, componentes.publicador)
        deudas = (
            lambda: UnidadDeudasSql(motor, cifrador),
            reloj,
            componentes.publicador,
            limitador,
            Limite(
                "gestion_deudas",
                config.limite_gestion_deudas,
                config.ventana_gestion_deudas_segundos,
            ),
            zona,
        )
        notificaciones = (lambda: UnidadNotificacionesSql(motor), reloj)
        pagos = (
            lambda: UnidadPagosSql(motor, cifrador),
            reloj,
            componentes.publicador,
            limitador,
            Limite(
                "gestion_pagos",
                config.limite_gestion_pagos,
                config.ventana_gestion_pagos_segundos,
            ),
            zona,
        )
        historial = (lambda: UnidadHistorialSql(motor, cifrador), reloj, zona)

        return cls(
            config=config,
            motor=motor,
            redis=redis,
            iniciar_sesion=IniciarSesion(
                unidad,
                contrasenas,
                limitador,
                limites,
                reloj,
                timedelta(minutes=config.sesion_duracion_minutos),
            ),
            autenticar=Autenticar(unidad, reloj),
            cerrar_sesion=CerrarSesion(unidad, reloj),
            cambiar_contrasena=CambiarContrasena(unidad, contrasenas, limitador, limites, reloj),
            crear_cuenta=CrearCuenta(unidad, contrasenas, reloj),
            consultar_documentos=ConsultarDocumentos(unidad, reloj),
            aceptar_documentos=AceptarDocumentos(unidad, reloj),
            consultar_cuenta=ConsultarCuenta(unidad, contrasenas, limitador, limites, reloj, zona),
            actualizar_datos_personales=ActualizarDatosPersonales(
                unidad, contrasenas, limitador, limites, reloj, zona
            ),
            cambiar_nombre_usuario=CambiarNombreUsuario(
                unidad, contrasenas, limitador, limites, reloj, zona
            ),
            confirmar_datos=ConfirmarDatos(unidad, limitador, limites, reloj),
            listar_equipo=ListarEquipo(*equipo),
            registrar_asistente=RegistrarAsistente(*equipo),
            bloquear_asistente=BloquearAsistente(*equipo),
            desbloquear_asistente=DesbloquearAsistente(*equipo),
            eliminar_asistente=EliminarAsistente(*equipo),
            recuperar_asistente=RecuperarAsistente(*equipo),
            restablecer_contrasena=RestablecerContrasena(*equipo),
            listar_categorias=ListarCategorias(*categorias),
            crear_categoria=CrearCategoria(*categorias),
            editar_categoria=EditarCategoria(*categorias),
            archivar_categoria=ArchivarCategoria(*categorias),
            reactivar_categoria=ReactivarCategoria(*categorias),
            consultar_reglas=ConsultarReglas(*reglas),
            cambiar_limite=CambiarLimite(*reglas),
            agregar_titular=AgregarTitular(*reglas),
            editar_titular=EditarTitular(*reglas),
            quitar_titular=QuitarTitular(*reglas),
            evaluar_documento=EvaluarDocumento(*reglas),
            componentes=componentes,
            subir_documento=SubirDocumento(
                *documentos,
                almacen=componentes.almacen,
                inspector=componentes.inspector,
                huellero=componentes.cifrador,
                cola=cola,
                limitador=limitador,
                limite=Limite(
                    "subida_documentos",
                    config.limite_subida_documentos,
                    config.ventana_subida_documentos_segundos,
                ),
            ),
            consultar_documento=ConsultarDocumento(*documentos),
            leer_contenido=LeerContenido(*documentos, almacen=componentes.almacen),
            listar_bloqueos=ListarBloqueos(*documentos),
            levantar_bloqueo=LevantarBloqueo(*documentos),
            registrar_deuda=RegistrarDeuda(*deudas),
            listar_deudas=ListarDeudas(*deudas),
            consultar_deuda=ConsultarDeuda(*deudas),
            consultar_calendario=ConsultarCalendario(*deudas),
            autorizar_deuda=AutorizarDeuda(*deudas),
            rechazar_deuda=RechazarDeuda(*deudas),
            dar_visto_bueno=DarVistoBueno(*deudas),
            anular_deuda=AnularDeuda(*deudas),
            listar_notificaciones=ListarNotificaciones(*notificaciones),
            marcar_leida=MarcarLeida(*notificaciones),
            marcar_todas_leidas=MarcarTodasLeidas(*notificaciones),
            suscriptor_avisos=SuscriptorRedis(config.redis_url),
            listar_por_pagar=ListarPorPagar(*pagos),
            subir_comprobante=SubirComprobante(
                *pagos,
                almacen=componentes.almacen,
                inspector=componentes.inspector,
                huellero=componentes.cifrador,
                cola=cola_comprobantes,
            ),
            consultar_comprobante=ConsultarComprobante(*pagos),
            leer_comprobante=LeerComprobante(*pagos, almacen=componentes.almacen),
            registrar_pago=RegistrarPago(*pagos),
            listar_pagos=ListarPagos(*pagos),
            listar_bloqueos_pagos=ListarBloqueosPagos(*pagos),
            levantar_bloqueo_pagos=LevantarBloqueoPagos(*pagos),
            consultar_pago=ConsultarPago(*pagos),
            confirmar_pago=ConfirmarPago(*pagos),
            devolver_pago=DevolverPago(*pagos),
            declarar_mora=DeclararMora(*pagos),
            listar_moras=ListarMoras(*pagos),
            consultar_mora=ConsultarMora(*pagos),
            aprobar_mora=AprobarMora(*pagos),
            rechazar_mora=RechazarMora(*pagos),
            pedir_pago=PedirPago(*pagos),
            retirar_pedido=RetirarPedido(*pagos),
            listar_pedidos=ListarPedidos(*pagos),
            consultar_historial=ConsultarHistorial(*historial),
            exportar_historial=ExportarHistorial(*historial),
        )

    def cerrar(self) -> None:
        self.motor.dispose()
        self.redis.close()
