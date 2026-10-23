<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../.github/assets/marca/logo-oscuro.svg">
  <img alt="Deconsta" src="../.github/assets/marca/logo-claro.svg" height="56">
</picture>

### Client · interfaz web

Vue 3 · TypeScript · Vite · Pinia · Vue Router · Tailwind CSS 4

[Estructura](#estructura) ·
[Identidad visual](#identidad-visual) ·
[Espacio y pestañas](#espacio-y-pestañas) ·
[Pantallas](#pantallas) ·
[Desarrollo](#desarrollo) ·
[Pruebas](#pruebas)

</div>

---

Una SPA con dos experiencias sobre la misma base: **gerencia** decide y **asistencia** ejecuta. El
frontend mejora la experiencia (validación mientras se escribe, prellenado desde el documento,
avisos en tiempo real, espera tras un 429), pero **la autoridad es siempre el backend**: cada
pantalla muestra junto al campo lo que la API responde.

<img src="../.github/assets/capturas/asistencia-registro-de-deuda.webp" alt="Registro de una deuda desde su documento">

## Estructura

El código se organiza **por funcionalidad**, no por tipo de archivo. Cada carpeta de `features/`
trae lo suyo: `api/`, `components/`, `composables/`, `stores/`, `views/`, `types.ts` y
`__tests__/`.

```txt
src/
  features/
    acceso/          inicio de sesión, contraseña y medidor de seguridad
    incorporacion/   primer ingreso: términos y privacidad, contraseña temporal y confirmación de datos
    espacio/         cabecera, pestañas por rol, tarjeta de la cuenta y secciones.ts
    panel/           Resumen de la gerencia y Mi jornada de la asistencia
    deudas/          registro desde el documento, cuotas y la mesa «Por autorizar»
    pagos/           por pagar, vouchers, verificación, moras y pedidos de pago
    calendario/      vencimientos por día, mes y próximos 14 días
    historial/       filtros, auditoría por deuda y exportación CSV
    notificaciones/  avisos guardados, flujo SSE y campana
    equipo/          alta, bloqueo, restablecimiento y eliminación de asistentes
    reglas/          límite en soles, titulares autorizados y su prueba
    categorias/      catálogo de colores e íconos, sugerencias y archivado
    cuenta/          datos personales, usuario y contraseña, permisos y privacidad
  shared/
    api/             cliente HTTP y estructura común de errores
    validaciones/    DNI, carné, celular, correo y nombres (mismas reglas que el backend)
    composables/     copiar al portapapeles, limpiar el error de un campo al editarlo
    components/      BaseBoton, BaseCampo, BaseAviso, BaseDialogo, BaseIcono, BaseAvatar,
                     MarcaDeconsta, CampoDocumento, DialogoFalloGuardado
  router/            rutas y guardas de navegación
  assets/main.css    Tailwind y los tokens de la identidad
```

## Identidad visual

Los tokens viven en `src/assets/main.css` como variables de Tailwind 4 (`@theme`), así que se usan
como clases (`bg-ciruela`, `text-tinta`, `border-borde`).

| Token                       | Color                                                                                                                                                                                                                         | Uso                             |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `ciruela`                   | ![#6B304F](https://img.shields.io/badge/%20-%20-6B304F?style=flat-square) `#6B304F`                                                                                                                                           | Marca y acento de la gerencia   |
| `eucalipto` (acento)        | ![#365C4B](https://img.shields.io/badge/%20-%20-365C4B?style=flat-square) `#365C4B`                                                                                                                                           | Acento de la asistencia         |
| `rosa`                      | ![#F1DDE7](https://img.shields.io/badge/%20-%20-F1DDE7?style=flat-square) `#F1DDE7`                                                                                                                                           | Fondos suaves del acento        |
| `tinta`                     | ![#302330](https://img.shields.io/badge/%20-%20-302330?style=flat-square) `#302330`                                                                                                                                           | Texto principal                 |
| `fondo`                     | ![#F7F5F7](https://img.shields.io/badge/%20-%20-F7F5F7?style=flat-square) `#F7F5F7`                                                                                                                                           | Fondo de la aplicación          |
| `exito` · `aviso` · `error` | ![#286849](https://img.shields.io/badge/%20-%20-286849?style=flat-square) ![#885D16](https://img.shields.io/badge/%20-%20-885D16?style=flat-square) ![#A33B40](https://img.shields.io/badge/%20-%20-A33B40?style=flat-square) | Estados, con su fondo `*-fondo` |

- **Tipografía:** Manrope variable (200–800), servida desde `public/fonts/` con su licencia OFL.
- **El acento sigue al rol:** `data-rol` en `<html>` cambia `--color-acento` a eucalipto para la asistencia. La marca siempre es ciruela.
- **La marca:** dos trazos inclinados de distinto largo, una obligación y su comprobación (`MarcaDeconsta.vue`). Los SVG del logotipo, el banner y los íconos están en [`.github/assets/marca/`](../.github/assets/marca/).
- **Íconos de la app:** `favicon.svg`, `favicon.ico` (16/32/48), `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` e `icon-maskable-512.png`, declarados en `site.webmanifest`.

## Espacio y pestañas

| Gerencia                                                                                 | Asistencia                                                    |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Resumen · Por autorizar · Por verificar · Por pagar · Calendario · Historial · Mi equipo | Mi jornada · Pagos por completar · Mis registros · Calendario |

**Registrar deuda** es una acción de la cabecera y los datos de la cuenta viven en la tarjeta que se
abre desde el avatar. `features/espacio/secciones.ts` es la única fuente de las secciones de cada
rol: de ahí salen las rutas, las pestañas y el menú. Para agregar una, se declara ahí con su `vista`;
mientras se construye usa `EnDesarrolloView`. Una sección con `pestana` es una pestaña dentro de
su página («Mi cuenta», «Límites y categorías»).

**Guardas.** Tras ingresar, la guarda lleva a `/bienvenida` mientras la sesión tenga
`pasos_pendientes` (aceptar los documentos vigentes o, para una asistente nueva, confirmar sus
datos). Con la contraseña temporal (`debe_cambiar_contrasena`), el espacio abre una ventana cerrable
en cada ingreso que la tarjeta de la cuenta sigue recordando.

## Pantallas

<details open>
<summary><b>Registrar deuda</b></summary>
<br>

El documento (foto o PDF de hasta 10 MB) se suelta o se elige, se muestra tal cual y se sube;
mientras el backend lo analiza, `useAnalisisDocumento` consulta su estado. «Lo que comprobamos»
resume las capas del análisis y si el documento ya respalda otra deuda.

- **Ilegible, alterado o repetido:** no se llenan datos. El repetido dice en qué deuda se usó y, al tercer intento de la asistente, que su registro quedó en pausa hasta que su gerente lo permita.
- **Listo:** el formulario llega prellenado y todo se corrige a mano. «Se paga en cuotas» abre las cuotas de un cronograma, con un generador mensual y cada cuota editable (`cuotas.ts` trabaja en céntimos). Si el análisis sugiere una categoría nueva, se crea ahí mismo.
- **Varios lugares de pago:** se marcan todos los que acepta la empresa; el voucher deberá ser de uno de ellos.
- Si la asistente corrige el importe o el código de pago, se le avisa que la deuda esperará autorización.

</details>

<details>
<summary><b>Por autorizar y Por verificar</b></summary>
<br>

Mesas de decisión de la gerencia: lista a la izquierda y detalle a la derecha. Cada deuda muestra su
documento (descargado con la sesión, sin enlaces públicos), las comprobaciones, los motivos y lo
corregido frente a lo leído. Cada pago muestra el voucher, lo leído, la **confianza** con su anillo y
los diez criterios con su resultado. Rechazar, anular y devolver piden un motivo.

<img src="../.github/assets/capturas/gerencia-por-verificar.webp" alt="Verificación de un pago">

</details>

<details>
<summary><b>Pagos, moras y pedidos</b></summary>
<br>

«Pagos por completar» separa lo vencido de lo que viene. Registrar un pago sube uno o varios
vouchers (un agente puede cobrar por partes), espera su análisis y, si la lectura falla, permite
escribir los datos a mano (`VoucherAMano`), con la confianza limitada. Una cuota vencida que se pagó
con más se declara como mora con su prueba. El gerente puede **pedir** a una asistente que pague una
cuota concreta, con una nota, y retirar el pedido.

</details>

<details>
<summary><b>Calendario e historial</b></summary>
<br>

El calendario muestra cada cuota en su día, con totales del mes, lo vencido y lo que espera
autorización, y se navega con el teclado. El historial filtra por texto, estado, categoría, fechas,
lugar, quién registró y quién pagó, despliega la auditoría de cada deuda y exporta CSV.

<img src="../.github/assets/capturas/historial-auditoria.webp" alt="Auditoría en el historial">

</details>

<details>
<summary><b>Notificaciones en tiempo real</b></summary>
<br>

Al entrar al espacio se abre un `EventSource` a `/api/v1/notificaciones/flujo`. Cada aviso nuevo
recarga la lista, la campana muestra cuántos faltan leer y un aviso en pantalla lo anuncia sin
quitar el foco. Las pantallas que dependen de los avisos (Por autorizar, Por verificar, el Resumen)
se refrescan solas.

</details>

<details>
<summary><b>Mi equipo, reglas y categorías</b></summary>
<br>

- **Mi equipo:** el gerente registra asistentes y elige o deja generar el usuario y la contraseña, que se muestran una sola vez para copiarlos. Si esa persona fue eliminada antes, se ofrece recuperar su cuenta.
- **Reglas:** el límite se escribe como en Perú («2,900.50») y un aviso dice cómo se guardará. Los titulares autorizados exigen confirmar que esa persona lo autorizó y su documento solo se ve enmascarado. «Prueba tus reglas» consulta la evaluación del backend sin guardar nada.
- **Categorías:** desde cero o desde una sugerencia, con color, ícono y vista previa; se archivan con motivo y se reactivan.

</details>

<details>
<summary><b>Mi cuenta y validaciones</b></summary>
<br>

Cuatro pestañas (`/cuenta`, `/cuenta/acceso`, `/cuenta/permisos`, `/cuenta/privacidad`) hijas de
`CuentaLayout`: cambiar de pestaña no recarga los datos.

- «Guardar» solo se activa con un cambio real: `datos.ts` normaliza igual que el backend.
- Cambiar el correo, el documento o el usuario pide la contraseña actual. El usuario se cambia hasta 3 veces por mes y el cupo restante está a la vista.
- Si un guardado falla, una ventana explica qué pasó; reintentar solo se ofrece cuando el fallo no depende de los datos.

`shared/validaciones/persona.ts` filtra lo que se escribe o pega: DNI de 8 dígitos, carné de 9 a 12
caracteres, celular peruano de 9 dígitos que empieza con 9, correo y nombres solo con letras.

</details>

## Desarrollo

```sh
pnpm install
pnpm dev          # http://localhost:5173; /api se reenvía a http://localhost:8000
```

La sesión viaja en una cookie `HttpOnly` y `SameSite=Strict`, así que la API debe servirse en el
mismo origen: en desarrollo lo resuelve el proxy de Vite y en producción Caddy (`Caddyfile`), que
también sirve los estáticos con caché inmutable y entrega el flujo SSE sin acumularlo.

| Comando           | Qué hace                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `pnpm dev`        | Servidor de desarrollo con recarga en caliente                           |
| `pnpm build`      | Revisión de tipos y construcción para producción                         |
| `pnpm type-check` | `vue-tsc` sobre toda la aplicación                                       |
| `pnpm lint`       | oxlint y ESLint con corrección automática (la CI no admite advertencias) |
| `pnpm format`     | Prettier sobre `src/`                                                    |

## Pruebas

```sh
pnpm test:unit                       # Vitest + Vue Test Utils (jsdom)
pnpm test:e2e --project=chromium     # Playwright; requiere la API y Postgres en marcha
```

- **Unitarias:** cada funcionalidad trae sus pruebas en `__tests__/`. La CI exige 70 % de cobertura de líneas.
- **De punta a punta:** `e2e/` crea cuentas nuevas con el comando del server y prueba flujos completos entre dos navegadores (la asistente registra, la gerencia autoriza en tiempo real). `e2e/deudas.spec.ts` necesita además el worker (`pnpm worker:ocr`).

> [!NOTE]
> La suite e2e completa hace más de 20 ingresos desde la misma IP y el límite por defecto es de 20
> por minuto: la última prueba puede recibir 429. Conviene correr los archivos por separado o
> esperar un minuto.
