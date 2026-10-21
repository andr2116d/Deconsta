# client

Interfaz web de Deconsta: Vue 3, Vite, TypeScript, Pinia, Vue Router y Tailwind CSS 4.

## Estructura

El código se organiza por funcionalidades:

```txt
src/
  features/
    acceso/          inicio de sesión y cambio de contraseña
      api/             llamadas a la API
      components/      formularios, medidor de seguridad y marco visual del acceso
      composables/     lógica reutilizable (indicador de seguridad de la contraseña)
      stores/          estado de la sesión (Pinia)
      views/           pantallas enrutadas
    incorporacion/   primer ingreso: aceptación de términos y privacidad, y la ventana de la
                     contraseña temporal
    espacio/         espacio de trabajo: cabecera, pestañas por rol y tarjeta de la cuenta
      layouts/         EspacioLayout, ruta padre de todas las secciones
      secciones.ts     secciones de cada rol; de aquí salen rutas, pestañas y menú
      views/           EnDesarrolloView, lugar de cada sección mientras se construye
    cuenta/          Mi cuenta: datos personales, usuario y contraseña, rol y permisos, privacidad
      layouts/         CuentaLayout: encabezado, pestañas y tarjeta lateral que se quedan al
                       cambiar de pestaña
      datos.ts         normalización igual a la del backend para detectar cambios reales
  shared/
    api/             cliente HTTP y estructura común de errores
    components/      componentes base (BaseBoton, BaseCampo, BaseAviso, BaseDialogo, BaseIcono,
                     BaseAvatar, MarcaDeconsta)
  router/            rutas y guardas de navegación
  assets/main.css    Tailwind y los tokens de la identidad (ciruela, rosa mineral, Manrope)
```

Tras ingresar, la guarda lleva a `/bienvenida` mientras la sesión tenga `pasos_pendientes` (la
aceptación de los documentos vigentes). Con la contraseña temporal (`debe_cambiar_contrasena`), el
espacio abre una ventana cerrable en cada ingreso; cerrarla la pospone hasta el siguiente ingreso y
la tarjeta de la cuenta la sigue recordando.

## Espacio y pestañas

Cada rol tiene sus pestañas: gerencia (Resumen, Por autorizar, Por verificar, Calendario,
Historial, Mi equipo) y asistencia (Mi jornada, Pagos por completar, Mis registros, Calendario).
Registrar deuda es una acción de la cabecera, y los datos de la cuenta viven en la tarjeta que se
abre desde el avatar. Para agregar o mover una sección se edita `features/espacio/secciones.ts`;
al construirla, se le asigna su `vista` y deja de usar `EnDesarrolloView`. Ocultar una sección a un rol solo ordena
la interfaz: el backend autoriza cada operación.
El acento de color sigue al rol (`data-rol` en `<html>`): ciruela para gerencia y eucalipto para
asistencia; la marca siempre es ciruela.

## Mi cuenta

Se abre desde la tarjeta del avatar. Sus cuatro pestañas (`/cuenta`, `/cuenta/acceso`,
`/cuenta/permisos` y `/cuenta/privacidad`) son rutas hijas de `CuentaLayout`, así que cambiar de
pestaña no recarga los datos. Los datos viven en el store `cuenta`; al guardar, la tarjeta lateral,
la cabecera y el menú se actualizan sin recargar.

- «Guardar» solo se activa con un cambio real: se compara con la misma normalización del backend.
- El número de documento no se cambia. Pasar de DNI a carné de extranjería pide dos advertencias
  al elegirlo y una confirmación final al guardar.
- Cambiar el correo, el documento o el usuario pide la contraseña actual. El usuario se cambia
  hasta 3 veces por mes y el cupo restante está a la vista.
- La nueva contraseña igual a la actual se advierte mientras se escribe.
- Si un guardado falla, una ventana explica qué pasó y qué campos revisar; reintentar solo se
  ofrece cuando el fallo no depende de los datos.
- `/cambiar-contrasena` redirige a la pestaña de usuario y contraseña.

Las pantallas siguen los prototipos de `DECONSTA/`. El frontend mejora la experiencia (validación
de campos, indicador de seguridad, espera tras un 429), pero la autoridad es siempre el backend.

## Desarrollo

```sh
pnpm install
pnpm dev          # http://localhost:5173; /api se reenvía a http://localhost:8000
```

La sesión viaja en una cookie HttpOnly y SameSite=Strict, así que la API debe servirse en el mismo
origen: en desarrollo lo resuelve el proxy de Vite y en producción el proxy del despliegue.

## Pruebas y validaciones

```sh
pnpm test:unit    # Vitest
pnpm type-check
pnpm lint
pnpm test:e2e --project=chromium   # Playwright; requiere la API y Postgres en marcha
```

Las pruebas de punta a punta crean cuentas nuevas con el comando del server
(`app.acceso.infraestructura.cli`) en la base de desarrollo. Cada ejecución hace unos 16 ingresos
desde la misma IP; el límite por defecto es de 20 por minuto, así que conviene esperar un minuto
entre ejecuciones seguidas.
