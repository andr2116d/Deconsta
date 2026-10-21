import base64
import binascii
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: Literal["desarrollo", "pruebas", "produccion"] = "desarrollo"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/deconsta"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]
    timezone: str = "America/Lima"
    # Aplica las migraciones pendientes al arrancar la API.
    migrar_al_iniciar: bool = True
    nivel_registro: str = "INFO"

    # Claves de 32 bytes en base64, distintas entre sí y fuera del repositorio. Generar con:
    # python -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"
    # clave_cifrado_datos cifra los datos personales (AES-256-GCM) y clave_huella_datos calcula
    # las huellas HMAC que permiten buscarlos y exigir unicidad sin descifrarlos.
    clave_cifrado_datos: SecretStr
    clave_huella_datos: SecretStr
    # Cifra los archivos de los documentos antes de subirlos al bucket (AES-256-GCM).
    clave_cifrado_archivos: SecretStr

    # Bucket privado compatible con S3: Railway Buckets en producción (estilo virtual, según su
    # pestaña Credentials) y SeaweedFS en desarrollo (estilo de ruta).
    s3_endpoint: str = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_bucket: str = "deconsta"
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_estilo_ruta: bool = True

    # Revisión de documentos con Claude. Sin clave, la revisión queda incompleta y lo que registra
    # una asistente espera la autorización del gerente.
    anthropic_api_key: SecretStr | None = None
    ia_modelo: str = "claude-sonnet-5-5"
    ia_esfuerzo: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    sesion_duracion_minutos: int = Field(default=480, ge=5, le=1440)
    cookie_sesion_nombre: str = "deconsta_sesion"
    # Solo se envía por HTTPS. Únicamente puede desactivarse en desarrollo local sobre http.
    cookie_segura: bool = True

    # Límites de frecuencia (solicitudes por ventana), compartidos entre instancias vía Redis.
    limite_ingreso_por_origen: int = Field(default=20, ge=1)
    ventana_ingreso_por_origen_segundos: int = Field(default=60, ge=1)
    limite_ingreso_por_usuario: int = Field(default=10, ge=1)
    ventana_ingreso_por_usuario_segundos: int = Field(default=900, ge=1)
    limite_cambio_contrasena: int = Field(default=5, ge=1)
    ventana_cambio_contrasena_segundos: int = Field(default=900, ge=1)
    limite_desbloqueo: int = Field(default=20, ge=1)
    ventana_desbloqueo_segundos: int = Field(default=3600, ge=1)
    # Actualizaciones de «Mi cuenta» (datos y usuario), que pueden pedir la contraseña actual.
    limite_actualizacion_cuenta: int = Field(default=10, ge=1)
    ventana_actualizacion_cuenta_segundos: int = Field(default=900, ge=1)
    # Altas, bloqueos, eliminaciones y recuperaciones de asistentes de un mismo gerente.
    limite_gestion_equipo: int = Field(default=30, ge=1)
    ventana_gestion_equipo_segundos: int = Field(default=3600, ge=1)
    # Altas, ediciones, archivos y reactivaciones de categorías de un mismo gerente.
    limite_gestion_categorias: int = Field(default=60, ge=1)
    ventana_gestion_categorias_segundos: int = Field(default=3600, ge=1)
    # Cambios del límite y de los titulares autorizados, y pruebas de las reglas, por gerente.
    limite_gestion_reglas: int = Field(default=60, ge=1)
    ventana_gestion_reglas_segundos: int = Field(default=3600, ge=1)
    # Documentos que sube una misma cuenta.
    limite_subida_documentos: int = Field(default=30, ge=1)
    ventana_subida_documentos_segundos: int = Field(default=3600, ge=1)
    # Registros y decisiones sobre deudas de una misma cuenta.
    limite_gestion_deudas: int = Field(default=120, ge=1)
    ventana_gestion_deudas_segundos: int = Field(default=3600, ge=1)

    @field_validator("clave_cifrado_datos", "clave_huella_datos", "clave_cifrado_archivos")
    @classmethod
    def validar_clave(cls, valor: SecretStr) -> SecretStr:
        try:
            crudo = base64.b64decode(valor.get_secret_value(), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("debe estar codificada en base64") from error
        if len(crudo) != 32:
            raise ValueError("debe tener 32 bytes")
        return valor

    @model_validator(mode="after")
    def validar_seguridad(self) -> Self:
        claves = {
            self.clave_cifrado_datos.get_secret_value(),
            self.clave_huella_datos.get_secret_value(),
            self.clave_cifrado_archivos.get_secret_value(),
        }
        if len(claves) < 3:
            raise ValueError(
                "clave_cifrado_datos, clave_huella_datos y clave_cifrado_archivos deben ser "
                "distintas"
            )
        if self.entorno == "produccion" and not self.cookie_segura:
            raise ValueError("En producción la cookie de sesión debe ser segura (HTTPS)")
        return self

    @property
    def clave_cifrado(self) -> bytes:
        return base64.b64decode(self.clave_cifrado_datos.get_secret_value())

    @property
    def clave_huella(self) -> bytes:
        return base64.b64decode(self.clave_huella_datos.get_secret_value())

    @property
    def clave_archivos(self) -> bytes:
        return base64.b64decode(self.clave_cifrado_archivos.get_secret_value())


# Las claves llegan del entorno o del .env; mypy no puede saberlo.
settings = Settings()  # type: ignore[call-arg]
