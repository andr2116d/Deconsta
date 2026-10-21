"""Errores del acceso. Cada uno trae un código estable para el frontend y un mensaje para la
persona usuaria: qué ocurrió y qué hacer. Ninguno incluye contraseñas, hashes ni detalles internos.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID


class ErrorAcceso(Exception):
    codigo = "ERROR_ACCESO"
    mensaje = "No pudimos completar la operación."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class CredencialesIncorrectas(ErrorAcceso):
    # Mismo mensaje para un usuario inexistente y para una contraseña incorrecta: no revela qué
    # usuarios existen.
    codigo = "CREDENCIALES_INCORRECTAS"
    mensaje = "Usuario o contraseña incorrectos. Revisa los datos e inténtalo de nuevo."


class CuentaBloqueada(ErrorAcceso):
    codigo = "CUENTA_BLOQUEADA"
    mensaje = (
        "Tu cuenta está bloqueada por varios intentos fallidos. "
        "Pide a tu gerente que la desbloquee para volver a ingresar."
    )

    def __init__(self, por_gerente: bool = False) -> None:
        super().__init__(
            "Tu gerente bloqueó tu cuenta. Pídele que la desbloquee para volver a ingresar."
            if por_gerente
            else None
        )


class DemasiadasSolicitudes(ErrorAcceso):
    codigo = "DEMASIADAS_SOLICITUDES"

    def __init__(self, reintentar_en: int) -> None:
        self.reintentar_en = max(1, reintentar_en)
        super().__init__(
            "Hiciste demasiados intentos seguidos. "
            f"Espera {_duracion(self.reintentar_en)} antes de volver a intentarlo."
        )


class NoAutenticado(ErrorAcceso):
    codigo = "NO_AUTENTICADO"
    mensaje = "Tu sesión terminó o no es válida. Inicia sesión para continuar."


class SinPermiso(ErrorAcceso):
    codigo = "SIN_PERMISO"
    mensaje = "Tu rol no permite realizar esta acción."


class CuentaNoEncontrada(ErrorAcceso):
    codigo = "CUENTA_NO_ENCONTRADA"
    mensaje = "No encontramos esa cuenta en tu equipo."


class CuentaYaBloqueada(ErrorAcceso):
    codigo = "CUENTA_YA_BLOQUEADA"
    mensaje = "Esta cuenta ya está bloqueada."


class PersonaYaEnEquipo(ErrorAcceso):
    """El documento corresponde a una asistente vigente del mismo equipo."""

    codigo = "PERSONA_YA_EN_EQUIPO"

    def __init__(self, bloqueada: bool) -> None:
        mensaje = (
            "Ya registraste a esta persona y su cuenta está bloqueada. Desbloquéala desde "
            "Mi equipo en lugar de crear otra."
            if bloqueada
            else "Esta persona ya es parte de tu equipo."
        )
        super().__init__(mensaje, campos={"numero_documento": mensaje})


class AsistenteEliminadaRegistrada(ErrorAcceso):
    """El documento corresponde a una asistente que este gerente eliminó: se ofrece recuperarla."""

    codigo = "ASISTENTE_ELIMINADA"
    mensaje = (
        "Ya habías registrado a esta persona y eliminaste su cuenta. Puedes recuperarla con su "
        "historial o crear una cuenta nueva desde cero."
    )

    def __init__(self, asistente_id: UUID, nombre_usuario: str) -> None:
        self.asistente_id = asistente_id
        self.nombre_usuario = nombre_usuario
        super().__init__()


class CuentaNoEliminada(ErrorAcceso):
    codigo = "CUENTA_NO_ELIMINADA"
    mensaje = "Esta cuenta no está eliminada: ya forma parte de tu equipo."


class DatosYaConfirmados(ErrorAcceso):
    codigo = "DATOS_YA_CONFIRMADOS"
    mensaje = "Ya confirmaste tus datos. Puedes actualizarlos desde Mi cuenta."


class CuentaNoBloqueada(ErrorAcceso):
    codigo = "CUENTA_NO_BLOQUEADA"
    mensaje = "Esta cuenta no está bloqueada. Puede ingresar con normalidad."


class ContrasenaActualIncorrecta(ErrorAcceso):
    codigo = "CONTRASENA_ACTUAL_INCORRECTA"
    mensaje = "La contraseña actual no es correcta."

    def __init__(self) -> None:
        super().__init__(campos={"contrasena_actual": self.mensaje})


class ContrasenaInsegura(ErrorAcceso):
    codigo = "CONTRASENA_INSEGURA"
    mensaje = "La nueva contraseña no cumple la política de seguridad."

    def __init__(self, requisitos: Mapping[str, str], campo: str = "contrasena_nueva") -> None:
        self.requisitos = dict(requisitos)
        super().__init__(campos={campo: " ".join(self.requisitos.values())})


class ContrasenaRepetida(ErrorAcceso):
    codigo = "CONTRASENA_REPETIDA"
    mensaje = "La nueva contraseña debe ser distinta de la actual."

    def __init__(self) -> None:
        super().__init__(campos={"contrasena_nueva": self.mensaje})


class DatosInvalidos(ErrorAcceso):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los datos marcados."


class DatosDuplicados(ErrorAcceso):
    codigo = "DATOS_DUPLICADOS"
    mensaje = "Ya existe una cuenta con alguno de estos datos."


class SinCambios(ErrorAcceso):
    codigo = "SIN_CAMBIOS"
    mensaje = "No hay cambios por guardar: los datos son iguales a los registrados."


class ContrasenaRequerida(ErrorAcceso):
    codigo = "CONTRASENA_REQUERIDA"
    mensaje = "Confirma este cambio con tu contraseña actual."

    def __init__(self) -> None:
        super().__init__(campos={"contrasena_actual": self.mensaje})


class DocumentoNoModificable(ErrorAcceso):
    """El documento identifica a la persona titular: cambiarlo sería cambiar de persona."""

    codigo = "DOCUMENTO_NO_MODIFICABLE"
    mensaje = (
        "Tu documento identifica a la persona titular de la cuenta y no se puede cambiar. "
        "Solo se admite pasar de DNI a carné de extranjería."
    )

    def __init__(self) -> None:
        super().__init__(campos={"numero_documento": self.mensaje})


class CambioDocumentoSinConfirmar(ErrorAcceso):
    codigo = "CAMBIO_DOCUMENTO_SIN_CONFIRMAR"
    mensaje = (
        "Pasar de DNI a carné de extranjería es un caso excepcional. Confirma expresamente el "
        "cambio para continuar."
    )


class LimiteCambiosNombreUsuario(ErrorAcceso):
    codigo = "LIMITE_CAMBIOS_USUARIO"

    def __init__(self, maximo: int, renueva_en: datetime) -> None:
        self.renueva_en = renueva_en
        super().__init__(
            f"Ya cambiaste tu usuario {maximo} veces este mes. Podrás volver a cambiarlo desde "
            f"el {_fecha(renueva_en)}.",
            campos={"nombre_usuario": f"Alcanzaste los {maximo} cambios de este mes."},
        )


class IncorporacionPendiente(ErrorAcceso):
    """La sesión es válida, pero la cuenta aún no completa los pasos de su primer ingreso."""

    codigo = "INCORPORACION_PENDIENTE"

    def __init__(self, pasos: Sequence[str]) -> None:
        self.pasos = list(pasos)
        super().__init__(
            "Acepta los términos de uso y la política de privacidad vigentes para continuar."
            if self.pasos and self.pasos[0] == "aceptar_documentos"
            else "Confirma tus datos personales para continuar."
        )


class DocumentosDesactualizados(ErrorAcceso):
    codigo = "DOCUMENTOS_DESACTUALIZADOS"
    mensaje = (
        "Los términos o la política de privacidad cambiaron mientras los leías. "
        "Revisa la versión vigente y vuelve a aceptarla."
    )


class ServicioNoDisponible(ErrorAcceso):
    codigo = "SERVICIO_NO_DISPONIBLE"
    mensaje = "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos."


MESES = (
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
).split()


def _fecha(momento: datetime) -> str:
    """Fecha en la zona del momento (la del negocio): «1 de noviembre»."""
    return f"{momento.day} de {MESES[momento.month - 1]}"


def _duracion(segundos: int) -> str:
    if segundos < 60:
        return f"{segundos} segundo{'s' if segundos != 1 else ''}"
    minutos = -(-segundos // 60)
    return f"{minutos} minuto{'s' if minutos != 1 else ''}"
