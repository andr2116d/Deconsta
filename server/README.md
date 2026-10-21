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
  categorias/      categorías del espacio (misma división en dominio, aplicacion e infraestructura)
  reglas/          reglas de autorización: límite en soles, titulares autorizados y evaluación
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
  --numero-documento 45678912 [--telefono 987654321] [--usuario valentina.ramos] \
  [--cargo "Gerente general"]
uv run python -m app.acceso.infraestructura.cli crear-asistente --gerente valentina.ramos ...
```

Imprime el id, el usuario y una contraseña temporal. `--tipo-documento` acepta `dni` o `ce`. El
cargo lo fija quien crea la cuenta; la persona no puede editarlo.

## Primer ingreso

Antes de entrar a su espacio, cada cuenta acepta los términos de uso y la política de privacidad
vigentes. Una asistente registrada desde Mi equipo (o recuperada) además confirma sus datos
(`completar_datos`): completa su correo y revisa lo que registró su gerente; en esa primera
confirmación aún puede corregir su documento. La sesión informa lo que falta en `pasos_pendientes`; mientras quede algo, las rutas de
trabajo (`GerenteDep`, `SesionHabilitadaDep`) responden 403 `INCORPORACION_PENDIENTE`.

Cambiar la contraseña temporal no bloquea el espacio: la sesión lo indica con
`debe_cambiar_contrasena` y el client lo recuerda en cada ingreso hasta que se cambie.

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
| `GET /api/v1/asistentes` | Asistentes del equipo (documento enmascarado) |
| `POST /api/v1/asistentes` | Registra una asistente y entrega su usuario y contraseña una sola vez |
| `POST /api/v1/asistentes/{id}/bloqueo` | El gerente bloquea a su asistente y cierra sus sesiones |
| `POST /api/v1/asistentes/{id}/desbloqueo` | El gerente desbloquea a su asistente |
| `POST /api/v1/asistentes/{id}/eliminacion` | Baja lógica: deja de ingresar, se conserva su historial |
| `POST /api/v1/asistentes/{id}/recuperacion` | Recupera una eliminada con una contraseña temporal nueva |
| `POST /api/v1/asistentes/{id}/restablecimiento` | Contraseña temporal nueva para una asistente que olvidó la suya |
| `GET /api/v1/cuenta` | Datos de la propia cuenta, descifrados, y el cupo de cambios de usuario |
| `POST /api/v1/cuenta/confirmacion-datos` | La asistente confirma sus datos en su primer ingreso |
| `POST /api/v1/cuenta/datos` | Actualiza los datos personales (envía los datos completos) |
| `POST /api/v1/cuenta/nombre-usuario` | Cambia el usuario (pide la contraseña actual) |
| `GET /api/v1/categorias` | Categorías activas del espacio; `?archivadas=true` suma las archivadas (gerente) |
| `POST /api/v1/categorias` | El gerente crea una categoría |
| `POST /api/v1/categorias/{id}/edicion` | Cambia nombre y descripción; sin color o ícono conserva los actuales |
| `POST /api/v1/categorias/{id}/archivado` | La retira de las deudas nuevas, con motivo opcional |
| `POST /api/v1/categorias/{id}/reactivacion` | Vuelve a ofrecerla |
| `GET /api/v1/reglas` | Límite y titulares autorizados del gerente (documentos enmascarados) |
| `POST /api/v1/reglas/limite` | Fija el límite (`"2900.50"`, como texto) o lo quita (`null`) |
| `POST /api/v1/reglas/titulares` | Agrega un titular autorizado (pide `autorizacion_declarada`) |
| `POST /api/v1/reglas/titulares/{id}/edicion` | Cambia nombre y relación; el documento no se edita |
| `POST /api/v1/reglas/titulares/{id}/eliminacion` | Baja lógica, con motivo opcional |
| `POST /api/v1/reglas/evaluacion` | Prueba las reglas con un documento de ejemplo; no guarda nada |

Los errores siguen siempre `{"code", "detail", "fields"?}`. La asistente se bloquea al quinto
intento fallido hasta que su gerente la desbloquee; el gerente no se bloquea. Aparte, el rate
limiting por IP y por usuario (en Redis, compartido entre instancias) responde 429 con
`Retry-After`.

Detrás de un proxy, arranca uvicorn con `--proxy-headers --forwarded-allow-ips=<ip del proxy>`
para que el límite por IP use la IP real del cliente. En producción: `ENTORNO=produccion`,
`COOKIE_SEGURA=true` y HTTPS en el borde.

## Mi equipo

El gerente administra a sus asistentes; cualquier otra cuenta responde 404. Las reglas viven en
`acceso/aplicacion/equipo.py`:

- Al registrar, el gerente da nombres, apellidos, celular y documento; el cargo es opcional. El
  usuario y la contraseña los elige él (se validan) o los genera Deconsta. Se muestran una sola vez.
- Una persona no puede tener dos cuentas vigentes: si ya está en el equipo (activa o bloqueada)
  responde `PERSONA_YA_EN_EQUIPO`; si es de otra cuenta, `DATOS_DUPLICADOS` sin decir de quién.
- Eliminar es una baja lógica (`eliminada_en`): la cuenta no ingresa (responde como inexistente),
  sus sesiones se cierran y el historial se conserva. Registrar de nuevo a esa persona responde
  `ASISTENTE_ELIMINADA` con `deleted_account`, para elegir entre recuperarla o crear otra con
  `crear_aunque_eliminada: true`. Recuperarla le da una contraseña temporal nueva y vuelve a
  pedirle confirmar sus datos.
- Restablecer la contraseña genera una temporal nueva (se muestra una sola vez), invalida la anterior,
  cierra sus sesiones y queda en la auditoría como `CONTRASENA_RESTABLECIDA` con su motivo. No
  levanta un bloqueo: eso se hace con el desbloqueo.
- Bloquear (causa `gerente`) cierra sus sesiones; el bloqueo por 5 intentos fallidos tiene la causa
  `intentos_fallidos`. El mensaje de ingreso dice cuál fue.
- El trabajo será del equipo, no de una asistente: eliminar a una no deja nada sin responsable.

## Categorías

Ordenan las deudas del espacio (agua, luz, tarjetas…) para filtrarlas, resumirlas y exportarlas.
Son del espacio del gerente y las comparte su equipo. Las reglas viven en `categorias/dominio`:

- Solo el gerente las crea, edita, archiva y reactiva; sus asistentes consultan las activas. El
  espacio sale de la sesión: la categoría de otro espacio responde 404 `CATEGORIA_NO_ENCONTRADA`.
- Nombre de 2 a 40 caracteres (letras, números, espacios y `. , & / ( ) ' + -`), único en el
  espacio sin distinguir mayúsculas, tildes ni espacios repetidos. Uno repetido responde 409
  `CATEGORIA_DUPLICADA`; si la otra está archivada, `existing_category` permite reactivarla.
- Descripción opcional de hasta 200 caracteres: qué documentos van ahí (servirá para la
  clasificación automática de los recibos). Color e ícono salen de catálogos fijos; sin ellos se
  asignan el siguiente color de la paleta y una etiqueta.
- Nunca se borran: archivar las retira de las deudas nuevas. Una archivada no se edita
  (`CATEGORIA_ARCHIVADA`) hasta reactivarla. Hay un tope de 50 activas (`LIMITE_CATEGORIAS`).
- Cada escritura toma la fila del gerente con `FOR UPDATE`, cuenta para el límite
  `LIMITE_GESTION_CATEGORIAS` y queda en la auditoría (`CATEGORIA_CREADA`, `_EDITADA`,
  `_ARCHIVADA`, `_REACTIVADA`) con quién, cuándo, el motivo y, al editar, el antes y el después.

## Reglas de autorización

Deciden qué de lo que registra una asistente espera la autorización del gerente. Solo el gerente
las consulta y las cambia. Las reglas viven en `reglas/dominio`:

- **Importe.** Espera autorización lo que supera el límite (estrictamente mayor). Sin límite, el
  importe no detiene nada. Los importes son soles con dos decimales, como texto y `Decimal`, nunca
  `float`; hasta S/ 9,999,999.99.
- **Titular.** Espera autorización el documento cuyo titular no es el gerente (su nombre, su
  documento y su nombre en recibos de Mi cuenta) ni un titular autorizado. Un documento sin
  titular legible (una boleta de menos de S/ 700 no identifica al comprador) no se marca.
- **Comparación de titulares.** Primero por documento: dos documentos distintos son dos personas, y
  un RUC 10 reconoce el DNI que contiene. Si falta alguno, por nombre: sin importar orden, tildes,
  mayúsculas, partículas («de», «los») ni iniciales («PEREZ GOMEZ JUAN C»), con al menos dos
  palabras completas.
- **Lo que registra el gerente** no espera a nadie; un titular distinto solo se le avisa.
- **Titulares autorizados.** Nombre (persona o razón social) y documento opcional: DNI, carné o RUC
  con su dígito verificador. Son datos personales de terceros (Ley 29733): exigen
  `autorizacion_declarada` (se guarda su fecha), se cifran con AES-256-GCM, se buscan por huellas
  HMAC, solo salen enmascarados y nunca van a la auditoría. No se repiten por nombre ni por
  documento, el gerente no puede agregarse a sí mismo (`TITULAR_ES_GERENTE`) y hay un tope de 20.
- Cada cambio toma la fila del gerente con `FOR UPDATE`, cuenta para `LIMITE_GESTION_REGLAS` y queda
  en la auditoría: `LIMITE_AUTORIZACION_CAMBIADO` (antes y después), `TITULAR_AUTORIZADO_AGREGADO`,
  `_EDITADO` (qué campos) y `_QUITADO` (con su motivo).

`reglas.dominio.evaluacion.evaluar` es la regla que aplicará el registro de deudas, y
`POST /reglas/evaluacion` la expone para que el gerente la pruebe.

Pendiente para ese módulo:

- avisar al gerente en tiempo real con una notificación persistente;
- no aceptar documentos repetidos. Cada documento se identificará por la huella SHA-256 del archivo
  y por una clave normalizada:
  - comprobante SUNAT: RUC del emisor, serie y número;
  - recibo de servicio: empresa, suministro y periodo;
  - voucher: entidad y número de operación.

## Validaciones de datos personales

- DNI: 8 dígitos. Carné de extranjería: de 9 a 12 letras o dígitos.
- Celular peruano: 9 dígitos que empiezan con 9; se acepta con `+51` y se guarda sin él.
- Correo: usuario, `@` y dominio con extensión (solo se comprueba la forma, no se envía nada).
- Nombres y apellidos: solo letras, espacios, apóstrofo, punto o guion.

## Mi cuenta

Cada cuenta consulta y actualiza solo sus propios datos; las rutas exigen la incorporación
completa. Las reglas viven en `acceso/dominio/cuenta.py`:

- Solo cuenta como cambio lo que difiere tras normalizar; si nada cambia, 422 `SIN_CAMBIOS`.
- El número de documento no se cambia (`DOCUMENTO_NO_MODIFICABLE`). La única excepción es pasar
  de DNI a carné de extranjería, con `confirmar_cambio_documento: true`; queda en la auditoría como
  `DOCUMENTO_CAMBIADO`.
- Cambiar el correo, el documento o el usuario pide `contrasena_actual`. Un intento con una
  contraseña incorrecta queda como `CONFIRMACION_CONTRASENA_FALLIDA`.
- El nombre como figura en los recibos (cifrado) es solo del gerente.
- El usuario se cambia como máximo 3 veces por mes calendario en la zona de `TIMEZONE`; el cuarto
  intento responde 409 `LIMITE_CAMBIOS_USUARIO` con `renews_at`. Los cambios quedan en
  `cambio_nombre_usuario`, que solo admite inserciones.
- La auditoría guarda qué campos cambiaron, nunca sus valores.

## Dependencias

```sh
uv add <paquete>           # dependencia de producción
uv add --dev <paquete>     # dependencia de desarrollo
uv remove <paquete>
uv lock --upgrade          # actualizar versiones
```
