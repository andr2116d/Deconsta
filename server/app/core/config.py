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

    @field_validator("clave_cifrado_datos", "clave_huella_datos")
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
        if self.clave_cifrado_datos == self.clave_huella_datos:
            raise ValueError("clave_cifrado_datos y clave_huella_datos deben ser distintas")
        if self.entorno == "produccion" and not self.cookie_segura:
            raise ValueError("En producción la cookie de sesión debe ser segura (HTTPS)")
        return self

    @property
    def clave_cifrado(self) -> bytes:
        return base64.b64decode(self.clave_cifrado_datos.get_secret_value())

    @property
    def clave_huella(self) -> bytes:
        return base64.b64decode(self.clave_huella_datos.get_secret_value())


# Las claves llegan del entorno o del .env; mypy no puede saberlo.
settings = Settings()  # type: ignore[call-arg]
