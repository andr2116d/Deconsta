from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.acceso.dominio.modelos import Rol, Usuario


def exigir(valor: str, mensaje: str) -> str:
    """Un campo vacío o con solo espacios cuenta como ausente, con un mensaje propio del campo."""
    if not valor.strip():
        raise PydanticCustomError("obligatorio", mensaje)
    return valor


class IngresoEntrada(BaseModel):
    # El valor por defecto vacío se valida: un campo ausente recibe el mismo mensaje que uno vacío.
    nombre_usuario: str = Field("", max_length=64, validate_default=True)
    contrasena: str = Field("", max_length=128, validate_default=True)

    @field_validator("nombre_usuario")
    @classmethod
    def validar_nombre_usuario(cls, valor: str) -> str:
        return exigir(valor, "Ingresa tu nombre de usuario.")

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, valor: str) -> str:
        return exigir(valor, "Ingresa tu contraseña.")


class CambioContrasenaEntrada(BaseModel):
    contrasena_actual: str = Field("", max_length=128, validate_default=True)
    # Mayor que la política para que una contraseña larga reciba el mensaje de la política.
    contrasena_nueva: str = Field("", max_length=256, validate_default=True)

    @field_validator("contrasena_actual")
    @classmethod
    def validar_actual(cls, valor: str) -> str:
        return exigir(valor, "Ingresa tu contraseña actual.")

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_nueva(cls, valor: str) -> str:
        return exigir(valor, "Ingresa la nueva contraseña.")


class DesbloqueoEntrada(BaseModel):
    motivo: str | None = Field(None, max_length=500)


class UsuarioSalida(BaseModel):
    """Solo lo que la interfaz necesita para saludar y decidir la navegación."""

    id: UUID
    nombre_usuario: str
    nombres: str
    rol: Rol

    @classmethod
    def desde(cls, usuario: Usuario) -> "UsuarioSalida":
        return cls(
            id=usuario.id,
            nombre_usuario=usuario.nombre_usuario,
            nombres=usuario.nombres,
            rol=usuario.rol,
        )


class SesionSalida(BaseModel):
    usuario: UsuarioSalida
    debe_cambiar_contrasena: bool


class IngresoSalida(SesionSalida):
    primer_ingreso: bool


class DesbloqueoSalida(BaseModel):
    id: UUID
    nombre_usuario: str
    bloqueada: bool


class ErrorSalida(BaseModel):
    """Forma común de los errores (documentación de OpenAPI)."""

    code: str
    detail: str
    fields: dict[str, str] | None = None
