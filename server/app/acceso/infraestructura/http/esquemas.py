from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.aplicacion.cuenta import CuentaPropia
from app.acceso.aplicacion.equipo import CredencialesEntregadas, MiembroEquipo
from app.acceso.dominio.datos_personales import TipoDocumento
from app.acceso.dominio.incorporacion import DocumentoVigente, PasoPendiente, TipoDocumentoLegal
from app.acceso.dominio.modelos import CausaBloqueo, Rol, Usuario
from app.core.esquemas import Entrada


def exigir(valor: str, mensaje: str) -> str:
    """Un campo vacío o con solo espacios cuenta como ausente, con un mensaje propio del campo."""
    if not valor.strip():
        raise PydanticCustomError("obligatorio", mensaje)
    return valor


class IngresoEntrada(Entrada):
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


class CambioContrasenaEntrada(Entrada):
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
    # En orden. Vacío: la cuenta puede entrar a su espacio.
    pasos_pendientes: list[PasoPendiente]

    @classmethod
    def desde(cls, sesion: SesionActiva) -> "SesionSalida":
        return cls(
            usuario=UsuarioSalida.desde(sesion.usuario),
            debe_cambiar_contrasena=sesion.usuario.debe_cambiar_contrasena,
            pasos_pendientes=list(sesion.pasos_pendientes),
        )


class IngresoSalida(SesionSalida):
    primer_ingreso: bool


class DocumentoAceptadoEntrada(Entrada):
    tipo: TipoDocumentoLegal
    # La versión que la persona leyó; se compara con la vigente.
    version: int = Field(ge=1)


class AceptacionEntrada(Entrada):
    documentos: list[DocumentoAceptadoEntrada] = Field(default_factory=list, max_length=10)


class SeccionSalida(BaseModel):
    titulo: str
    parrafos: list[str]


class DocumentoSalida(BaseModel):
    tipo: TipoDocumentoLegal
    version: int
    titulo: str
    resumen: str
    secciones: list[SeccionSalida]
    vigente_desde: datetime
    aceptado_en: datetime | None

    @classmethod
    def desde(cls, vigente: DocumentoVigente) -> "DocumentoSalida":
        documento = vigente.documento
        return cls(
            tipo=documento.tipo,
            version=documento.version,
            titulo=documento.titulo,
            resumen=documento.resumen,
            secciones=[
                SeccionSalida(titulo=s.titulo, parrafos=list(s.parrafos))
                for s in documento.secciones
            ],
            vigente_desde=documento.vigente_desde,
            aceptado_en=vigente.aceptado_en,
        )


class EspacioSalida(BaseModel):
    """Estado real del espacio de trabajo: los módulos aún no están disponibles."""

    usuario: UsuarioSalida
    disponible: bool


class DatosPersonalesEntrada(Entrada):
    """Los datos completos tal como quedarán. Las reglas (formato, qué cambia y qué no) las aplica
    el dominio; aquí solo se acotan los tamaños."""

    nombres: str = Field("", max_length=200)
    apellidos: str = Field("", max_length=200)
    correo: str = Field("", max_length=254)
    telefono: str | None = Field(None, max_length=30)
    tipo_documento: str = Field("", max_length=10)
    numero_documento: str = Field("", max_length=30)
    nombre_recibos: str | None = Field(None, max_length=200)
    # Solo se exige si cambia el correo o el documento.
    contrasena_actual: str | None = Field(None, max_length=128)
    # Pasar de DNI a carné de extranjería exige esta confirmación expresa.
    confirmar_cambio_documento: bool = False


class NombreUsuarioEntrada(Entrada):
    nombre_usuario: str = Field("", max_length=64, validate_default=True)
    contrasena_actual: str = Field("", max_length=128, validate_default=True)

    @field_validator("nombre_usuario")
    @classmethod
    def validar_nombre_usuario(cls, valor: str) -> str:
        return exigir(valor, "Escribe tu nuevo usuario.")

    @field_validator("contrasena_actual")
    @classmethod
    def validar_contrasena(cls, valor: str) -> str:
        return exigir(valor, "Confirma el cambio con tu contraseña actual.")


class CambiosNombreUsuarioSalida(BaseModel):
    maximo: int
    usados: int
    restantes: int
    # Inicio del mes siguiente en la hora del negocio: desde entonces vuelve a haber cupo.
    renueva_en: datetime


class CuentaSalida(BaseModel):
    """Datos de la propia cuenta, descifrados solo para ella."""

    id: UUID
    rol: Rol
    nombre_usuario: str
    nombres: str
    apellidos: str
    # Nulo solo mientras una asistente recién registrada no confirma sus datos.
    correo: str | None
    telefono: str | None
    tipo_documento: TipoDocumento
    numero_documento: str
    # Solo el gerente; en una asistente siempre es nulo.
    nombre_recibos: str | None
    cargo: str | None
    debe_cambiar_contrasena: bool
    contrasena_actualizada_en: datetime
    cambios_nombre_usuario: CambiosNombreUsuarioSalida

    @classmethod
    def desde(cls, cuenta: CuentaPropia) -> "CuentaSalida":
        usuario, datos, cupo = cuenta.usuario, cuenta.ficha.datos, cuenta.cambios_nombre_usuario
        return cls(
            id=usuario.id,
            rol=usuario.rol,
            nombre_usuario=usuario.nombre_usuario,
            nombres=datos.nombres,
            apellidos=datos.apellidos,
            correo=datos.correo,
            telefono=datos.telefono,
            tipo_documento=datos.tipo_documento,
            numero_documento=datos.numero_documento,
            nombre_recibos=datos.nombre_recibos,
            cargo=cuenta.ficha.cargo,
            debe_cambiar_contrasena=usuario.debe_cambiar_contrasena,
            contrasena_actualizada_en=usuario.contrasena_actualizada_en,
            cambios_nombre_usuario=CambiosNombreUsuarioSalida(
                maximo=cupo.maximo,
                usados=cupo.usados,
                restantes=cupo.restantes,
                renueva_en=cupo.renueva_en,
            ),
        )


class ConfirmacionDatosEntrada(Entrada):
    """Datos que la asistente revisa y completa en su primer ingreso."""

    nombres: str = Field("", max_length=200)
    apellidos: str = Field("", max_length=200)
    correo: str = Field("", max_length=300)
    telefono: str = Field("", max_length=30)
    tipo_documento: str = Field("", max_length=10)
    numero_documento: str = Field("", max_length=30)


class NuevaAsistenteEntrada(Entrada):
    nombres: str = Field("", max_length=200)
    apellidos: str = Field("", max_length=200)
    telefono: str = Field("", max_length=30)
    tipo_documento: str = Field("", max_length=10)
    numero_documento: str = Field("", max_length=30)
    cargo: str | None = Field(None, max_length=120)
    # Nulos o vacíos: Deconsta los genera.
    nombre_usuario: str | None = Field(None, max_length=64)
    contrasena: str | None = Field(None, max_length=256)
    # La persona fue eliminada de este equipo y el gerente prefiere una cuenta nueva.
    crear_aunque_eliminada: bool = False


class MotivoEntrada(Entrada):
    motivo: str | None = Field(None, max_length=500)


def enmascarar(numero: str) -> str:
    """El gerente reconoce el documento por sus últimos dígitos; no necesita verlo completo."""
    return f"•••• {numero[-4:]}"


class AsistenteSalida(BaseModel):
    id: UUID
    nombre_usuario: str
    nombres: str
    apellidos: str
    cargo: str | None
    telefono: str | None
    correo: str | None
    tipo_documento: TipoDocumento
    documento: str
    # activa, bloqueada o pendiente (aún no confirma sus datos en su primer ingreso).
    estado: str
    causa_bloqueo: CausaBloqueo | None
    bloqueada: bool
    debe_cambiar_contrasena: bool
    ultimo_ingreso_en: datetime | None

    @classmethod
    def desde(cls, miembro: MiembroEquipo) -> "AsistenteSalida":
        usuario, datos = miembro.usuario, miembro.ficha.datos
        if usuario.bloqueada:
            estado = "bloqueada"
        elif usuario.debe_confirmar_datos:
            estado = "pendiente"
        else:
            estado = "activa"
        return cls(
            id=usuario.id,
            nombre_usuario=usuario.nombre_usuario,
            nombres=datos.nombres,
            apellidos=datos.apellidos,
            cargo=miembro.ficha.cargo,
            telefono=datos.telefono,
            correo=datos.correo,
            tipo_documento=datos.tipo_documento,
            documento=enmascarar(datos.numero_documento),
            estado=estado,
            causa_bloqueo=usuario.causa_bloqueo,
            bloqueada=usuario.bloqueada,
            debe_cambiar_contrasena=usuario.debe_cambiar_contrasena,
            ultimo_ingreso_en=usuario.ultimo_ingreso_en,
        )


class CredencialesSalida(BaseModel):
    """Se muestran una sola vez para copiarlas; Deconsta no vuelve a conocer la contraseña."""

    asistente: AsistenteSalida
    nombre_usuario: str
    contrasena_temporal: str

    @classmethod
    def desde(cls, entregadas: CredencialesEntregadas) -> "CredencialesSalida":
        return cls(
            asistente=AsistenteSalida.desde(entregadas.miembro),
            nombre_usuario=entregadas.miembro.usuario.nombre_usuario,
            contrasena_temporal=entregadas.contrasena,
        )


class ErrorSalida(BaseModel):
    """Forma común de los errores (documentación de OpenAPI)."""

    code: str
    detail: str
    fields: dict[str, str] | None = None
