"""Archivos en un bucket privado compatible con S3: Railway Buckets en producción y SeaweedFS en
desarrollo.

Cada archivo se cifra en la aplicación con AES-256-GCM antes de salir del servidor, con su clave
de objeto como dato asociado: ni quien tenga acceso al bucket puede leerlo, y un objeto copiado a
otra clave no se descifra. El bucket nunca entrega enlaces públicos ni prefirmados: el archivo
llega al navegador por la API, después de comprobar el permiso.
"""

import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.documentos.dominio.modelos import TipoArchivo
from app.documentos.dominio.puertos import ErrorAlmacen

VERSION = b"\x01"
LONGITUD_NONCE = 12


class CifradorArchivos:
    def __init__(self, clave: bytes) -> None:
        self._aes = AESGCM(clave)

    def cifrar(self, contenido: bytes, contexto: str) -> bytes:
        nonce = os.urandom(LONGITUD_NONCE)
        return VERSION + nonce + self._aes.encrypt(nonce, contenido, contexto.encode())

    def descifrar(self, datos: bytes, contexto: str) -> bytes:
        if datos[:1] != VERSION:
            raise ErrorAlmacen("Versión de cifrado desconocida")
        nonce, cifrado = datos[1 : 1 + LONGITUD_NONCE], datos[1 + LONGITUD_NONCE :]
        try:
            return self._aes.decrypt(nonce, cifrado, contexto.encode())
        except InvalidTag as error:
            raise ErrorAlmacen("El archivo no corresponde a su clave o fue alterado") from error


class AlmacenS3:
    def __init__(
        self,
        cifrador: CifradorArchivos,
        *,
        endpoint: str,
        region: str,
        bucket: str,
        clave_acceso: str,
        clave_secreta: str,
        estilo_ruta: bool,
    ) -> None:
        self._cifrador = cifrador
        self._bucket = bucket
        self._cliente: Any = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=clave_acceso,
            aws_secret_access_key=clave_secreta,
            config=Config(
                s3={"addressing_style": "path" if estilo_ruta else "virtual"},
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def guardar(self, clave: str, contenido: bytes, tipo: TipoArchivo) -> None:
        try:
            self._cliente.put_object(
                Bucket=self._bucket,
                Key=clave,
                Body=self._cifrador.cifrar(contenido, clave),
                # Lo guardado es el cifrado: para el bucket es un binario sin tipo.
                ContentType="application/octet-stream",
                Metadata={"version-cifrado": "1"},
            )
        except (BotoCoreError, ClientError) as error:
            raise ErrorAlmacen(f"No se pudo guardar el objeto ({type(error).__name__})") from error

    def leer(self, clave: str) -> bytes:
        try:
            objeto = self._cliente.get_object(Bucket=self._bucket, Key=clave)
            datos = objeto["Body"].read()
        except (BotoCoreError, ClientError) as error:
            raise ErrorAlmacen(f"No se pudo leer el objeto ({type(error).__name__})") from error
        return self._cifrador.descifrar(datos, clave)
