import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)


class ProtectorArgon2:
    """Hash de contraseñas con Argon2id y los parámetros recomendados por RFC 9106 (perfil de
    memoria reducida). La contraseña nunca se guarda ni se cifra de forma reversible."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher()
        self._hash_ficticio = self._hasher.hash("contraseña-ficticia-para-igualar-tiempos")

    def generar_hash(self, contrasena: str) -> str:
        return self._hasher.hash(contrasena)

    def verificar(self, contrasena_hash: str, contrasena: str) -> bool:
        try:
            return self._hasher.verify(contrasena_hash, contrasena)
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError):
            logger.warning("Hash de contraseña ilegible; se rechaza el intento")
            return False

    def necesita_rehash(self, contrasena_hash: str) -> bool:
        return self._hasher.check_needs_rehash(contrasena_hash)

    def simular_verificacion(self, contrasena: str) -> None:
        self.verificar(self._hash_ficticio, contrasena)
