from app.acceso.aplicacion.crear_cuenta import generar_contrasena_temporal, sugerir_nombre_usuario
from app.acceso.dominio import politica_contrasena


def test_la_contrasena_temporal_cumple_la_politica() -> None:
    temporal = generar_contrasena_temporal("valentina.ramos")
    assert politica_contrasena.evaluar(temporal, nombre_usuario="valentina.ramos") == {}


def test_sugiere_un_usuario_sin_tildes() -> None:
    assert sugerir_nombre_usuario("Lucía María", "Peña Vega") == "lucia.pena"
