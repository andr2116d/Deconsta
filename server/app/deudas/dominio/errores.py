"""Errores de las deudas. Cada uno trae un código estable para el frontend y un mensaje que dice
qué ocurrió y qué hacer."""

from collections.abc import Mapping


class ErrorDeudas(Exception):
    codigo = "ERROR_DEUDAS"
    mensaje = "No pudimos completar la operación con la deuda."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class DeudaInvalida(ErrorDeudas):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los datos marcados."


class DeudaNoEncontrada(ErrorDeudas):
    codigo = "DEUDA_NO_ENCONTRADA"
    mensaje = "No encontramos esa deuda en tu espacio."


class TransicionInvalida(ErrorDeudas):
    codigo = "ESTADO_NO_PERMITE"


class CategoriaNoDisponible(ErrorDeudas):
    codigo = "CATEGORIA_NO_DISPONIBLE"

    def __init__(self) -> None:
        mensaje = "Esa categoría no está disponible en tu espacio. Elige otra o deja «Otros»."
        super().__init__(mensaje, campos={"categoria_id": mensaje})


class DocumentoNoRegistrable(ErrorDeudas):
    """El documento no puede respaldar una deuda. El código dice por qué."""

    MENSAJES = {
        "DOCUMENTO_EN_ANALISIS": "Todavía estamos revisando el documento. Espera unos segundos.",
        "DOCUMENTO_ILEGIBLE": (
            "El documento no se pudo leer, así que no puede respaldar una deuda. Sube una foto "
            "nítida o el PDF original."
        ),
        "DOCUMENTO_REPETIDO": "Este documento ya respalda otra deuda. Sube el de la nueva deuda.",
        "DOCUMENTO_RECHAZADO": (
            "El documento muestra señales de alteración y no puede respaldar una deuda. Sube el "
            "documento original que entregó el emisor."
        ),
        "DOCUMENTO_FALLIDO": (
            "No pudimos terminar de revisar el documento. Súbelo otra vez en unos minutos."
        ),
        "DOCUMENTO_YA_USADO": "Este documento ya respalda otra deuda. Sube el de la nueva deuda.",
    }

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        mensaje = self.MENSAJES[codigo]
        super().__init__(mensaje, campos={"documento_id": mensaje})
