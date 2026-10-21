import psycopg
import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings
from app.core.migraciones import ErrorMigracion, conninfo
from app.main import app, crear_app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_el_arranque_aplica_las_migraciones_pendientes(base_vacia: str) -> None:
    config = Settings(database_url=base_vacia, migrar_al_iniciar=True)
    with TestClient(crear_app(config)):
        pass
    with psycopg.connect(conninfo(base_vacia)) as conexion:
        registro = conexion.execute("SELECT to_regclass('migracion_aplicada')").fetchone()
    assert registro is not None and registro[0] == "migracion_aplicada"


def test_una_migracion_fallida_impide_arrancar(monkeypatch: pytest.MonkeyPatch) -> None:
    def fallar(_: str) -> list[int]:
        raise ErrorMigracion("La migración 0002_x falló y se revirtió")

    monkeypatch.setattr(main, "aplicar_pendientes", fallar)
    config = Settings(migrar_al_iniciar=True)
    with pytest.raises(ErrorMigracion), TestClient(crear_app(config)):
        pass
