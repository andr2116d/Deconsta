# server

API de Deconsta con FastAPI y arquitectura hexagonal. Las dependencias se manejan con
[uv](https://docs.astral.sh/uv/).

## Preparar

```sh
uv sync                # crea .venv e instala dependencias (incluye el grupo dev)
uv sync --group ocr    # además PaddleOCR, solo para el worker de la cola ocr
cp .env.example .env
# Genera tres claves distintas para CLAVE_CIFRADO_DATOS, CLAVE_HUELLA_DATOS y
# CLAVE_CIFRADO_ARCHIVOS:
python -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Las claves cifran los datos personales y los documentos en reposo; si se pierden, esos datos no se
recuperan. En producción viven en el gestor de secretos del despliegue, nunca en el repositorio.
`ANTHROPIC_API_KEY` sale de la Claude Console (una suscripción de Claude no sirve para una app
desplegada); sin ella, la revisión con IA queda incompleta y lo que registra una asistente espera
la autorización del gerente.

## Comandos

```sh
uv run uvicorn app.main:app --reload --port 8000   # servidor en desarrollo
uv run --group ocr celery -A app.workers.celery_app:celery_app worker -Q ocr --concurrency=1
PRUEBAS_OCR=1 uv run --group ocr pytest tests/test_adaptadores_documentos.py   # con PaddleOCR real
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
  documentos/      documentos de las deudas: subida, análisis en tres capas y bloqueos por repetidos
    infraestructura/ bucket S3 cifrado, inspector, PaddleOCR, Claude, Postgres, Celery y HTTP
  deudas/          registro de deudas, sus cuotas y las decisiones del gerente
  notificaciones/  notificaciones persistentes y avisos en tiempo real (Redis y SSE)
  workers/         aplicación de Celery; la tarea de análisis vive en documentos
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
| `POST /api/v1/documentos` | Sube el documento (multipart `archivo`); responde 202 «analizando» |
| `GET /api/v1/documentos/{id}` | Estado, señales y datos propuestos del análisis |
| `GET /api/v1/documentos/{id}/contenido` | El archivo descifrado, para quien lo subió y su gerente |
| `GET /api/v1/registro-deudas/bloqueos` | Asistentes con el registro de deudas bloqueado (gerente) |
| `POST /api/v1/registro-deudas/bloqueos/{id}/levantamiento` | El gerente levanta el bloqueo |
| `POST /api/v1/deudas` | Registra una deuda desde un documento listo |
| `GET /api/v1/deudas` | Deudas del espacio (gerente) o las propias (asistente); `?pendientes=true` |
| `GET /api/v1/deudas/{id}` | Detalle con sus cuotas y el análisis de su documento |
| `POST /api/v1/deudas/{id}/autorizacion` | El gerente autoriza lo que espera su autorización |
| `POST /api/v1/deudas/{id}/rechazo` | La rechaza, con motivo |
| `POST /api/v1/deudas/{id}/revision` | Le da su visto bueno: sale de sus pendientes |
| `POST /api/v1/deudas/{id}/anulacion` | La anula, con motivo |
| `GET /api/v1/notificaciones` | Las últimas 50 y cuántas faltan leer |
| `POST /api/v1/notificaciones/{id}/lectura` | Marca una como leída; `POST /notificaciones/lectura`, todas |
| `GET /api/v1/notificaciones/flujo` | Avisos en tiempo real (Server-Sent Events) |

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

- El gerente las crea, edita, archiva y reactiva; sus asistentes consultan las activas y crean
  nuevas (al registrar una deuda que no encaja), pero no las editan, archivan ni reactivan. El
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

`reglas.dominio.evaluacion.evaluar` es la regla que aplica el registro de deudas, y
`POST /reglas/evaluacion` la expone para que el gerente la pruebe.

## Documentos de las deudas

Toda deuda nace de un documento legible (recibo, boleta, factura, cronograma, papeleta, tributo).
Las reglas viven en `documentos/dominio`:

- **Archivo.** PDF, JPG, PNG o WebP de hasta 10 MB y 10 páginas; el tipo sale de sus primeros
  bytes. Un PDF con contraseña o dañado, o una imagen diminuta, se rechaza con su código.
- **Guardado.** Se cifra con AES-256-GCM (`CLAVE_CIFRADO_ARCHIVOS`, con la clave del objeto como
  contexto) y va a un bucket privado compatible con S3. El navegador nunca recibe enlaces: el
  archivo sale por la API, solo para quien lo subió y su gerente, con `no-store` y una CSP sin
  scripts. El nombre original y lo leído (titular, código de pago) se guardan cifrados.
- **Análisis**, en el worker de la cola `ocr` (`documentos.analizar`, con reintentos; si los
  agota, el documento queda `fallido`):
  1. PaddleOCR lee el texto. Si no se lee, es `ilegible`: no se registra ni se llega a la IA.
  2. Claude (`IA_MODELO`, por defecto `claude-sonnet-5-5`) clasifica, propone los datos (concepto,
     emisor, titular, código de pago, importe, vencimiento, cuotas de un cronograma, categoría y
     lugar de pago) y da un veredicto. El documento es un dato, nunca una instrucción. Lo
     propuesto se contrasta con el texto leído: un importe o un código que no aparece es una señal.
  3. Metadatos: editores de imágenes (riesgo alto), editores de PDF, procesadores de texto, PDF
     guardados después de generarse o con JavaScript (riesgo medio).
- **Riesgo.** Alto: lo que sube una asistente queda `rechazado`; al gerente solo se le advierte.
  Medio (incluida la revisión con IA incompleta): la deuda espera la autorización del gerente.
- **Repetidos.** Un documento respalda una sola deuda del espacio: lo impiden la huella HMAC del
  archivo, la clave de negocio (emisor y serie y número; empresa, suministro y periodo; entidad y
  crédito) y, si no hay clave, los números largos del texto. La base lo garantiza con índices
  únicos. Repetirlo responde 409 `DOCUMENTO_YA_REGISTRADO` con `existing_debt`.
- **Bloqueo.** Al tercer intento de una asistente en 24 horas se bloquea su registro de deudas (no
  su cuenta), queda `REGISTRO_DEUDAS_BLOQUEADO` en la auditoría y se notifica al gerente, el único
  que lo levanta. Los intentos anteriores a un levantamiento ya no cuentan. Al gerente nunca se le
  bloquea.

## Deudas

Las reglas viven en `deudas/dominio`:

- Se registra solo desde un documento propio y `listo`, con concepto, lugar de pago (`ventanilla`,
  `agente`, `banca_digital`, `transferencia`, `billetera`, `debito_automatico`), categoría
  opcional («Otros») y una o varias cuotas en soles con fechas en orden. Un recibo es una cuota; un
  cronograma, las suyas, con importes que pueden variar. El importe es la suma.
- Lo propuesto se corrige a mano, pero el límite y los titulares se aplican con lo que dice el
  documento: bajar el importe o poner al gerente como titular no evita la autorización. Corregir
  el importe o el código de pago la pide (`DATOS_CORREGIDOS`). Lo corregido queda en
  `campos_corregidos` para el gerente.
- Lo que registra una asistente queda `por_autorizar` (no se paga) si supera el límite, tiene otro
  titular, su documento es dudoso o se corrigió; si no, `registrada` con la revisión pendiente:
  se paga, y el gerente le da su visto bueno o la anula. Ambos casos se le notifican al gerente.
- El gerente autoriza o rechaza lo que espera, y da el visto bueno o anula lo registrado; rechazar
  y anular piden motivo. La deuda se toma con `FOR UPDATE`: una segunda decisión responde 409
  `ESTADO_NO_PERMITE`. Cada paso queda en la auditoría (`DEUDA_REGISTRADA`, `_AUTORIZADA`,
  `_RECHAZADA`, `_REVISADA`, `_ANULADA`) y se notifica a la asistente.
- Lo que registra el gerente queda `registrada` sin esperar a nadie: solo se le advierte.

## Notificaciones

Se guardan en la transacción del evento que las origina, con una clave de evento única por
destinatario, y no llevan nombres ni documentos. Después de confirmar, se anuncian por pub/sub de
Redis y `GET /notificaciones/flujo` las empuja a las sesiones abiertas; el cliente recarga la lista.

## Despliegue en Railway

- Servicios: la API, el worker de la cola `ocr` (instalado con `uv sync --group ocr`; los PDF se
  rasterizan con pdfium, sin poppler; reserva de 2 a 4 GB de memoria), Postgres, Redis y un
  Railway Bucket privado.
- Variables del bucket: las de su pestaña Credentials en `S3_ENDPOINT`, `S3_BUCKET`,
  `S3_ACCESS_KEY` y `S3_SECRET_KEY`, con `S3_ESTILO_RUTA=false`.
- `ANTHROPIC_API_KEY`, las tres claves de cifrado, `ENTORNO=produccion` y `COOKIE_SEGURA=true`.

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
