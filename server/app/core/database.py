from sqlalchemy import Engine, create_engine


def crear_motor(database_url: str) -> Engine:
    # hide_parameters: si una consulta falla, el log no muestra sus valores (datos personales
    # cifrados, huellas o hashes), solo la sentencia.
    return create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
