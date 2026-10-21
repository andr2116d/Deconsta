"""Las tareas del worker nunca dejan un archivo «analizando» para siempre."""

from uuid import uuid4

import pytest

from app.documentos.infraestructura import tareas as tareas_documentos
from app.pagos.infraestructura import tareas as tareas_pagos


class Falla:
    def ejecutar(self, _: object) -> None:
        raise NotImplementedError("ConvertPirAttribute2RuntimeAttribute not support")


class Marca:
    marcados: list[object] = []

    def __init__(self, *_: object) -> None: ...

    def ejecutar(self, identificador: object) -> None:
        Marca.marcados.append(identificador)


@pytest.mark.parametrize(
    ("modulo", "tarea", "marcador"),
    [
        (tareas_documentos, "analizar_documento", "MarcarAnalisisFallido"),
        (tareas_pagos, "analizar_comprobante", "MarcarComprobanteFallido"),
    ],
)
def test_un_error_inesperado_deja_el_analisis_fallido(
    monkeypatch: pytest.MonkeyPatch, modulo: object, tarea: str, marcador: str
) -> None:
    identificador = uuid4()
    Marca.marcados = []
    monkeypatch.setattr(modulo, "_analizar", Falla)
    monkeypatch.setattr(modulo, marcador, Marca)
    monkeypatch.setattr(
        modulo, "componentes", lambda: type("C", (), {"unidad": None, "publicador": None})()
    )

    assert getattr(modulo, tarea).run(str(identificador)) is None
    assert Marca.marcados == [identificador]
