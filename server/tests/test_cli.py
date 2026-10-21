import re

import pytest

from app.acceso.infraestructura import cli
from app.core.config import Settings
from tests.conftest import consultar

PERSONA = [
    "--nombres", "Valentina",
    "--apellidos", "Ramos Díaz",
    "--correo", "valentina@ejemplo.pe",
    "--tipo-documento", "dni",
    "--numero-documento", "45678912",
]  # fmt: skip


def test_crea_un_gerente_y_su_asistente(
    base: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "settings", Settings(database_url=base))

    assert cli.main(["crear-gerente", *PERSONA]) == 0
    salida = capsys.readouterr().out
    assert "Usuario: valentina.ramos" in salida
    assert re.search(r"^Id: [0-9a-f-]{36}$", salida, re.MULTILINE)
    assert "Contraseña temporal: " in salida

    asistente = [
        "--gerente", "valentina.ramos",
        "--nombres", "Lucía",
        "--apellidos", "Vega",
        "--correo", "lucia@ejemplo.pe",
        "--tipo-documento", "ce",
        "--numero-documento", "001234567",
    ]  # fmt: skip
    assert cli.main(["crear-asistente", *asistente]) == 0
    assert consultar(base, "SELECT rol, debe_cambiar_contrasena FROM usuario ORDER BY rol") == [
        ("asistente", True),
        ("gerente", True),
    ]


def test_rechaza_datos_duplicados_sin_crear_la_cuenta(
    base: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "settings", Settings(database_url=base))
    cli.main(["crear-gerente", *PERSONA])

    assert cli.main(["crear-gerente", *PERSONA, "--usuario", "otra.cuenta"]) == 1
    assert "Ya existe una cuenta" in capsys.readouterr().err
    assert consultar(base, "SELECT count(*) FROM usuario") == [(1,)]
