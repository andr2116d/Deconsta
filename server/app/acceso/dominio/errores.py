"""Errores del acceso. Cada uno trae un código estable para el frontend y un mensaje para la
persona usuaria: qué ocurrió y qué hacer. Ninguno incluye contraseñas, hashes ni detalles internos.
"""

from collections.abc import Mapping


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

    def __init__(self, requisitos: Mapping[str, str]) -> None:
        self.requisitos = dict(requisitos)
        super().__init__(campos={"contrasena_nueva": " ".join(self.requisitos.values())})


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


class ServicioNoDisponible(ErrorAcceso):
    codigo = "SERVICIO_NO_DISPONIBLE"
    mensaje = "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos."


def _duracion(segundos: int) -> str:
    if segundos < 60:
        return f"{segundos} segundo{'s' if segundos != 1 else ''}"
    minutos = -(-segundos // 60)
    return f"{minutos} minuto{'s' if minutos != 1 else ''}"
