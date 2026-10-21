"""Adaptadores reales de los documentos: el bucket S3 (SeaweedFS de compose), el inspector y, si
se pide con PRUEBAS_OCR=1, PaddleOCR (necesita uv sync --group ocr y descarga sus modelos)."""

import io
import os
import socket
import uuid

import pytest
from PIL import Image

from app.core.config import Settings
from app.documentos.dominio.errores import ArchivoInvalido, PdfProtegido
from app.documentos.dominio.modelos import TipoArchivo
from app.documentos.dominio.puertos import ErrorAlmacen
from app.documentos.infraestructura.almacen_s3 import AlmacenS3, CifradorArchivos
from app.documentos.infraestructura.inspector import InspectorArchivosLocal
from tests.dobles import imagen, pdf


def _s3_disponible() -> bool:
    try:
        socket.create_connection(("localhost", 8333), timeout=1).close()
    except OSError:
        return False
    return True


@pytest.mark.skipif(not _s3_disponible(), reason="SeaweedFS no está en marcha (pnpm services:up)")
def test_el_bucket_guarda_el_archivo_cifrado_y_lo_devuelve_intacto() -> None:
    config = Settings()  # type: ignore[call-arg]
    almacen = AlmacenS3(
        CifradorArchivos(config.clave_archivos),
        endpoint=config.s3_endpoint,
        region=config.s3_region,
        bucket=config.s3_bucket,
        clave_acceso=config.s3_access_key.get_secret_value(),
        clave_secreta=config.s3_secret_key.get_secret_value(),
        estilo_ruta=True,
    )
    clave = f"pruebas/{uuid.uuid4()}"
    contenido = imagen(1)
    almacen.guardar(clave, contenido, TipoArchivo.PNG)

    assert almacen.leer(clave) == contenido
    crudo = almacen._cliente.get_object(Bucket=config.s3_bucket, Key=clave)["Body"].read()
    assert contenido not in crudo
    # Otra clave de cifrado no lo abre.
    ajeno = AlmacenS3(
        CifradorArchivos(os.urandom(32)),
        endpoint=config.s3_endpoint,
        region=config.s3_region,
        bucket=config.s3_bucket,
        clave_acceso=config.s3_access_key.get_secret_value(),
        clave_secreta=config.s3_secret_key.get_secret_value(),
        estilo_ruta=True,
    )
    with pytest.raises(ErrorAlmacen):
        ajeno.leer(clave)
    almacen._cliente.delete_object(Bucket=config.s3_bucket, Key=clave)


def test_el_inspector_lee_el_programa_del_exif() -> None:
    lienzo = Image.new("RGB", (800, 600), "white")
    exif = Image.Exif()
    exif[0x0131] = "Adobe Photoshop 26.1 (Windows)"
    salida = io.BytesIO()
    lienzo.save(salida, format="JPEG", exif=exif)

    examen = InspectorArchivosLocal().examinar(salida.getvalue(), TipoArchivo.JPEG)
    assert examen.metadatos.programas == ("Adobe Photoshop 26.1 (Windows)",)


def test_el_inspector_rechaza_imagenes_diminutas_y_pdf_protegidos() -> None:
    inspector = InspectorArchivosLocal()
    diminuta = io.BytesIO()
    Image.new("RGB", (120, 80)).save(diminuta, format="PNG")
    with pytest.raises(ArchivoInvalido, match="muy pequeña"):
        inspector.examinar(diminuta.getvalue(), TipoArchivo.PNG)

    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf())))
    escritor.encrypt("secreta")
    protegido = io.BytesIO()
    escritor.write(protegido)
    with pytest.raises(PdfProtegido):
        inspector.examinar(protegido.getvalue(), TipoArchivo.PDF)


@pytest.mark.skipif(os.environ.get("PRUEBAS_OCR") != "1", reason="Activa con PRUEBAS_OCR=1")
def test_paddle_lee_un_recibo() -> None:
    from PIL import ImageDraw, ImageFont

    from app.documentos.infraestructura.lector_paddle import LectorPaddle

    lienzo = Image.new("RGB", (1200, 400), "white")
    dibujo = ImageDraw.Draw(lienzo)
    fuente = ImageFont.load_default(size=40)
    dibujo.text((40, 60), "Suministro: 54871236", fill="black", font=fuente)
    dibujo.text((40, 160), "TOTAL A PAGAR S/ 182.40", fill="black", font=fuente)
    salida = io.BytesIO()
    lienzo.save(salida, format="PNG")

    lectura = LectorPaddle().leer(salida.getvalue(), TipoArchivo.PNG)
    assert "54871236" in lectura.texto
    assert "182.40" in lectura.texto
    assert lectura.confianza > 0.8
