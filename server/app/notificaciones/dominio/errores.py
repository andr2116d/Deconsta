"""Errores de las notificaciones, con un código estable para el frontend."""


class ErrorNotificaciones(Exception):
    codigo = "ERROR_NOTIFICACIONES"
    mensaje = "No pudimos completar la operación con la notificación."

    def __init__(self, mensaje: str | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        super().__init__(self.mensaje)


class NotificacionNoEncontrada(ErrorNotificaciones):
    codigo = "NOTIFICACION_NO_ENCONTRADA"
    mensaje = "No encontramos esa notificación entre las tuyas."
