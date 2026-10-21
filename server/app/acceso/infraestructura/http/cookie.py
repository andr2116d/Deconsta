from fastapi import Response

from app.core.config import Settings


def borrar_cookie_sesion(respuesta: Response, config: Settings) -> None:
    """Borra la cookie de sesión con los mismos atributos con que se creó: así el navegador la
    reconoce como la misma y no queda una copia con otras reglas."""
    respuesta.delete_cookie(
        config.cookie_sesion_nombre,
        path="/api",
        secure=config.cookie_segura,
        httponly=True,
        samesite="strict",
    )
