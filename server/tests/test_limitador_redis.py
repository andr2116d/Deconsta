from redis import Redis

from app.acceso.dominio.puertos import Limite
from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.limitador_redis import LimitadorRedis

LIMITE = Limite("prueba", maximo=2, ventana_segundos=30)


def test_cuenta_por_identificador_y_avisa_cuando_reintentar(redis_limpio: Redis) -> None:
    limitador = LimitadorRedis(redis_limpio, CifradorDatos(b"k" * 32, b"h" * 32))
    # Dos limitadores con el mismo Redis simulan dos instancias de la API.
    otra_instancia = LimitadorRedis(redis_limpio, CifradorDatos(b"k" * 32, b"h" * 32))

    assert limitador.consumir(LIMITE, "10.0.0.1").permitido
    assert otra_instancia.consumir(LIMITE, "10.0.0.1").permitido
    rechazado = limitador.consumir(LIMITE, "10.0.0.1")

    assert not rechazado.permitido
    assert 0 < rechazado.reintentar_en <= 30
    assert limitador.consumir(LIMITE, "10.0.0.2").permitido
    # El identificador no se guarda en claro.
    assert not any(b"10.0.0" in clave for clave in redis_limpio.keys("*"))
