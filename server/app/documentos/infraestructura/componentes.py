"""Adaptadores de los documentos, compartidos por la API y el worker.

El lector de texto se crea siempre, pero solo carga PaddleOCR la primera vez que lee: la API no lo
usa y no necesita el grupo de dependencias ocr.
"""

from dataclasses import dataclass

from redis import Redis
from sqlalchemy import Engine

from app.acceso.infraestructura.cifrado import CifradorDatos
from app.core.config import Settings
from app.documentos.dominio.puertos import (
    Almacen,
    FabricaUnidadDocumentos,
    InspectorArchivos,
    LectorTexto,
    RevisorIa,
)
from app.documentos.infraestructura.almacen_s3 import AlmacenS3, CifradorArchivos
from app.documentos.infraestructura.inspector import InspectorArchivosLocal
from app.documentos.infraestructura.lector_paddle import LectorPaddle
from app.documentos.infraestructura.persistencia import UnidadDocumentosSql
from app.documentos.infraestructura.revisor_claude import RevisorClaude
from app.notificaciones.dominio.puertos import PublicadorAvisos
from app.notificaciones.infraestructura.avisos_redis import PublicadorRedis


@dataclass
class Componentes:
    cifrador: CifradorDatos
    almacen: Almacen
    inspector: InspectorArchivos
    lector: LectorTexto
    revisor: RevisorIa
    publicador: PublicadorAvisos
    unidad: FabricaUnidadDocumentos

    @classmethod
    def crear(cls, config: Settings, motor: Engine, redis: Redis | None = None) -> "Componentes":
        cifrador = CifradorDatos(config.clave_cifrado, config.clave_huella)
        redis = redis or Redis.from_url(
            config.redis_url, socket_timeout=2, socket_connect_timeout=2
        )
        clave_api = config.anthropic_api_key
        return cls(
            cifrador=cifrador,
            almacen=AlmacenS3(
                CifradorArchivos(config.clave_archivos),
                endpoint=config.s3_endpoint,
                region=config.s3_region,
                bucket=config.s3_bucket,
                clave_acceso=config.s3_access_key.get_secret_value(),
                clave_secreta=config.s3_secret_key.get_secret_value(),
                estilo_ruta=config.s3_estilo_ruta,
            ),
            inspector=InspectorArchivosLocal(),
            lector=LectorPaddle(),
            revisor=RevisorClaude(
                clave_api.get_secret_value() if clave_api else None,
                config.ia_modelo,
                config.ia_esfuerzo,
            ),
            publicador=PublicadorRedis(redis),
            unidad=lambda: UnidadDocumentosSql(motor, cifrador),
        )
