from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/deconsta"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]
    timezone: str = "America/Lima"
    # Aplica las migraciones pendientes al arrancar la API.
    migrar_al_iniciar: bool = True


settings = Settings()
