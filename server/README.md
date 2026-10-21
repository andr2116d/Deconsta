# server

API de Deconsta con FastAPI y arquitectura hexagonal. Las dependencias se manejan con
[uv](https://docs.astral.sh/uv/).

## Preparar

```sh
uv sync                # crea .venv e instala dependencias (incluye el grupo dev)
cp .env.example .env
# Genera dos claves distintas para CLAVE_CIFRADO_DATOS y CLAVE_HUELLA_DATOS:
python -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Las claves cifran los datos personales en reposo; si se pierden, esos datos no se recuperan. En
producción viven en el gestor de secretos del despliegue, nunca en el repositorio.

## Comandos

```sh
uv run uvicorn app.main:app --reload --port 8000   # servidor en desarrollo
uv run celery -A app.workers.celery_app:celery_app worker -Q general --loglevel=INFO
uv run pytest                                      # tests (usan Postgres y Redis de compose)
uv run ruff check . && uv run ruff format .        # lint y formato
uv run mypy app                                    # tipos
uv run python -m app.core.migraciones estado       # migraciones aplicadas y pendientes
uv run python -m app.core.migraciones aplicar      # aplicar sin arrancar la API
```

## Estructura

```txt
app/
  core/            configuración, base de datos, migraciones, errores y registro compartidos
  acceso/          inicio de sesión, sesiones, contraseñas y bloqueo de asistentes
    dominio/         entidades, reglas y puertos (sin dependencias de infraestructura)
    aplicacion/      casos de uso
    infraestructura/ adaptadores: Postgres, Redis, Argon2id, cifrado, HTTP y CLI
  contenedor.py    conecta los casos de uso con sus adaptadores
migraciones/       NNNN_descripcion.sql
```

## Migraciones

Cada archivo `migraciones/NNNN_descripcion.sql` es una versión. Al arrancar, la API toma un
advisory lock de Postgres, aplica en orden las pendientes (cada una en su transacción) y las
registra en `migracion_aplicada` con su checksum. Si una falla, se revierte y la API no arranca.
Una migración aplicada no se edita: los cambios van en un archivo nuevo.

## Cuentas

```sh
uv run python -m app.acceso.infraestructura.cli crear-gerente --nombres "Valentina" \
  --apellidos "Ramos Díaz" --correo valentina@ejemplo.pe --tipo-documento dni \
  --numero-documento 45678912 [--telefono 987654321] [--usuario valentina.ramos]
uv run python -m app.acceso.infraestructura.cli crear-asistente --gerente valentina.ramos ...
```

Imprime el id, el usuario y una contraseña temporal. `--tipo-documento` acepta `dni` o `ce`.

## Primer ingreso

Antes de entrar a su espacio, cada cuenta completa en orden: cambiar la contraseña temporal y
aceptar los términos de uso y la política de privacidad vigentes. La sesión informa lo que falta
en `pasos_pendientes`; mientras quede algo, las rutas de trabajo (`GerenteDep`,
`SesionHabilitadaDep`) responden 403 `INCORPORACION_PENDIENTE`.

Los documentos viven en `documento_legal` con su versión y no se editan. Para cambiar un texto,
crea una migración que inserte la versión siguiente (puede llevar `vigente_desde` futura): desde
que rige, todas las cuentas deben volver a aceptarla. Las aceptaciones quedan en
`aceptacion_documento` (cuenta, versión y fecha) y no se pueden modificar.

## Acceso

| Ruta | Descripción |
|---|---|
| `POST /api/v1/auth/login` | Inicia sesión y deja el token en una cookie HttpOnly |
| `GET /api/v1/auth/me` | Usuario de la sesión |
| `POST /api/v1/auth/logout` | Cierra la sesión |
| `POST /api/v1/auth/contrasena` | Cambia la contraseña (pide la actual) |
| `GET /api/v1/documentos-legales` | Términos y política vigentes, con su aceptación |
| `POST /api/v1/documentos-legales/aceptacion` | Acepta las versiones vigentes (`{tipo, version}`) |
| `GET /api/v1/espacio` | Entrada al espacio; exige la incorporación completa |
| `POST /api/v1/asistentes/{id}/desbloqueo` | El gerente desbloquea a su asistente |

Los errores siguen siempre `{"code", "detail", "fields"?}`. La asistente se bloquea al quinto
intento fallido hasta que su gerente la desbloquee; el gerente no se bloquea. Aparte, el rate
limiting por IP y por usuario (en Redis, compartido entre instancias) responde 429 con
`Retry-After`.

Detrás de un proxy, arranca uvicorn con `--proxy-headers --forwarded-allow-ips=<ip del proxy>`
para que el límite por IP use la IP real del cliente. En producción: `ENTORNO=produccion`,
`COOKIE_SEGURA=true` y HTTPS en el borde.

## Dependencias

```sh
uv add <paquete>           # dependencia de producción
uv add --dev <paquete>     # dependencia de desarrollo
uv remove <paquete>
uv lock --upgrade          # actualizar versiones
```
