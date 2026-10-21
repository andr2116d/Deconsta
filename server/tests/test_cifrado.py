import pytest

from app.acceso.infraestructura.cifrado import CifradorDatos, ErrorDescifrado


def test_el_cifrado_es_aleatorio_y_atado_a_su_contexto() -> None:
    cifrador = CifradorDatos(b"k" * 32, b"h" * 32)
    uno = cifrador.cifrar("45678912", "usuario.numero_documento:1")
    dos = cifrador.cifrar("45678912", "usuario.numero_documento:1")

    assert uno != dos and b"45678912" not in uno
    assert cifrador.descifrar(uno, "usuario.numero_documento:1") == "45678912"
    with pytest.raises(ErrorDescifrado):
        cifrador.descifrar(uno, "usuario.numero_documento:2")
    assert cifrador.huella("a") == cifrador.huella("a") != cifrador.huella("b")
