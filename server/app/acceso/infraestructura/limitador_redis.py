import logging

from redis import Redis, RedisError

from app.acceso.dominio.errores import ServicioNoDisponible
from app.acceso.dominio.puertos import Cupo, Limite
from app.acceso.infraestructura.cifrado import CifradorDatos

logger = logging.getLogger(__name__)

# Ventana fija atómica: incrementa y fija la expiración en un solo paso, aunque varias instancias
# de la API atiendan solicitudes a la vez.
CONSUMIR = """
local actual = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end
return {actual, ttl}
"""


class LimitadorRedis:
    """Limitador compartido en Redis. Los identificadores (IP, usuario) se guardan como huella
    HMAC, no en claro. Si Redis no responde, rechaza la solicitud en vez de dejarla pasar."""

    def __init__(self, cliente: Redis, cifrador: CifradorDatos, prefijo: str = "deconsta") -> None:
        self._script = cliente.register_script(CONSUMIR)
        self._cifrador = cifrador
        self._prefijo = prefijo

    def consumir(self, limite: Limite, identificador: str) -> Cupo:
        huella = self._cifrador.huella(f"{limite.ambito}:{identificador}").hex()[:32]
        clave = f"{self._prefijo}:limite:{limite.ambito}:{huella}"
        try:
            actual, ttl = self._script(keys=[clave], args=[limite.ventana_segundos])
        except RedisError:
            logger.exception("No se pudo consultar el límite de solicitudes en Redis")
            raise ServicioNoDisponible() from None
        permitido = int(actual) <= limite.maximo
        return Cupo(permitido, 0 if permitido else int(ttl))
