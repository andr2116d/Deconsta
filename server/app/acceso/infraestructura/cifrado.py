import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Primer byte del texto cifrado: permite rotar clave o algoritmo sin ambigüedad.
VERSION = b"\x01"
LONGITUD_NONCE = 12


class ErrorDescifrado(Exception):
    """El dato no corresponde a la clave o al contexto, o fue alterado."""


class CifradorDatos:
    """Cifrado en reposo de datos personales con AES-256-GCM y huellas HMAC-SHA256.

    El contexto (tabla, campo e id de la fila) va como dato asociado: un valor cifrado copiado a
    otra fila u otro campo no se descifra.
    """

    def __init__(self, clave_cifrado: bytes, clave_huella: bytes) -> None:
        self._aes = AESGCM(clave_cifrado)
        self._clave_huella = clave_huella

    def cifrar(self, texto: str, contexto: str) -> bytes:
        nonce = os.urandom(LONGITUD_NONCE)
        return VERSION + nonce + self._aes.encrypt(nonce, texto.encode(), contexto.encode())

    def descifrar(self, datos: bytes, contexto: str) -> str:
        if datos[:1] != VERSION:
            raise ErrorDescifrado("Versión de cifrado desconocida")
        nonce, cifrado = datos[1 : 1 + LONGITUD_NONCE], datos[1 + LONGITUD_NONCE :]
        try:
            return self._aes.decrypt(nonce, cifrado, contexto.encode()).decode()
        except InvalidTag as error:
            raise ErrorDescifrado("El dato cifrado no es válido para este contexto") from error

    def huella(self, valor: str) -> bytes:
        return hmac.new(self._clave_huella, valor.encode(), hashlib.sha256).digest()
