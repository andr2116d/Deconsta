"""Raíz de composición: conecta los casos de uso con sus adaptadores concretos."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis import Redis
from sqlalchemy import Engine

from app.acceso.aplicacion.autenticar import Autenticar, CerrarSesion
from app.acceso.aplicacion.crear_cuenta import CrearCuenta
from app.acceso.aplicacion.iniciar_sesion import IniciarSesion
from app.acceso.aplicacion.limites import LimitesAcceso
from app.acceso.dominio.puertos import Limite
from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.contrasenas import ProtectorArgon2
from app.acceso.infraestructura.limitador_redis import LimitadorRedis
from app.acceso.infraestructura.persistencia import UnidadDeTrabajoSql
from app.core.config import Settings
from app.core.database import crear_motor


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
    )


@dataclass
class Contenedor:
    config: Settings
    motor: Engine
    redis: Redis
    iniciar_sesion: IniciarSesion
    autenticar: Autenticar
    cerrar_sesion: CerrarSesion
    crear_cuenta: CrearCuenta

    @classmethod
    def crear(cls, config: Settings) -> "Contenedor":
        motor = crear_motor(config.database_url)
        cifrador = CifradorDatos(config.clave_cifrado, config.clave_huella)
        redis = Redis.from_url(config.redis_url, socket_timeout=2, socket_connect_timeout=2)
        limitador = LimitadorRedis(redis, cifrador)
        contrasenas = ProtectorArgon2()
        limites = limites_de(config)
        reloj = ahora_utc

        def unidad() -> UnidadDeTrabajoSql:
            return UnidadDeTrabajoSql(motor, cifrador)

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
            crear_cuenta=CrearCuenta(unidad, contrasenas, reloj),
        )

    def cerrar(self) -> None:
        self.motor.dispose()
        self.redis.close()
