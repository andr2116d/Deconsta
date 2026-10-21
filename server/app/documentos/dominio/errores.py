"""Errores de los documentos de las deudas. Cada uno trae un código estable para el frontend y un
mensaje que dice qué ocurrió y qué hacer, sin datos de otras personas."""

from collections.abc import Mapping
from datetime import datetime

from app.documentos.dominio.modelos import DeudaDelDocumento


class ErrorDocumentos(Exception):
    codigo = "ERROR_DOCUMENTOS"
    mensaje = "No pudimos completar la operación con el documento."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class ArchivoInvalido(ErrorDocumentos):
    codigo = "ARCHIVO_INVALIDO"
    mensaje = "Sube una imagen JPG, PNG o WebP, o un PDF del documento."

    def __init__(self, mensaje: str | None = None) -> None:
        mensaje = mensaje or self.mensaje
        super().__init__(mensaje, campos={"archivo": mensaje})


class ArchivoFaltante(ErrorDocumentos):
    codigo = "CAMPOS_OBLIGATORIOS"
    mensaje = "Elige el documento que respalda la deuda: una foto o el PDF del recibo."

    def __init__(self) -> None:
        super().__init__(campos={"archivo": self.mensaje})


class ArchivoVacio(ArchivoInvalido):
    codigo = "ARCHIVO_VACIO"
    mensaje = "El archivo está vacío. Elige el documento otra vez."


class ArchivoDemasiadoGrande(ArchivoInvalido):
    codigo = "ARCHIVO_DEMASIADO_GRANDE"
    mensaje = "El archivo supera los 10 MB. Sube una foto o un PDF más liviano."


class PdfProtegido(ArchivoInvalido):
    codigo = "PDF_PROTEGIDO"
    mensaje = "El PDF tiene contraseña. Descárgalo sin protección y vuelve a subirlo."


class DemasiadasPaginas(ArchivoInvalido):
    codigo = "DEMASIADAS_PAGINAS"

    def __init__(self, maximo: int) -> None:
        super().__init__(f"El PDF tiene más de {maximo} páginas. Sube solo las del documento.")


class DocumentoYaRegistrado(ErrorDocumentos):
    """El documento ya respalda otra deuda del espacio."""

    codigo = "DOCUMENTO_YA_REGISTRADO"

    def __init__(self, deuda: DeudaDelDocumento, *, registro_bloqueado: bool) -> None:
        self.deuda = deuda
        self.registro_bloqueado = registro_bloqueado
        mensaje = (
            f"Este documento ya se usó en la deuda «{deuda.concepto}». Sube el documento de la "
            "deuda que quieres registrar."
        )
        if registro_bloqueado:
            mensaje += (
                " Como ya lo intentaste varias veces, tu gerente deberá permitirte registrar "
                "deudas otra vez."
            )
        super().__init__(mensaje, campos={"archivo": mensaje})


class RegistroBloqueado(ErrorDocumentos):
    codigo = "REGISTRO_DEUDAS_BLOQUEADO"

    def __init__(self, desde: datetime) -> None:
        self.desde = desde
        super().__init__(
            "No puedes registrar deudas por ahora: intentaste varias veces usar documentos que ya "
            "respaldan otras deudas. Tu gerente ya lo sabe y puede permitirlo otra vez desde Mi "
            "equipo. Puedes seguir con tus demás tareas."
        )


class DocumentoNoEncontrado(ErrorDocumentos):
    codigo = "DOCUMENTO_NO_ENCONTRADO"
    mensaje = "No encontramos ese documento entre los tuyos."


class ContenidoNoDisponible(ErrorDocumentos):
    codigo = "SERVICIO_NO_DISPONIBLE"
    mensaje = "No pudimos traer el archivo en este momento. Inténtalo de nuevo en unos minutos."


class BloqueoNoEncontrado(ErrorDocumentos):
    codigo = "BLOQUEO_NO_ENCONTRADO"
    mensaje = "Esa asistente puede registrar deudas: no tiene un bloqueo vigente."


class AsistenteNoEncontrada(ErrorDocumentos):
    codigo = "CUENTA_NO_ENCONTRADA"
    mensaje = "No encontramos a esa asistente en tu equipo."
