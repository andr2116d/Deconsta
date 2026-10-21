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
    proximamente/    pantalla temporal tras ingresar
  shared/
    api/             cliente HTTP y estructura común de errores
    components/      componentes base (BaseBoton, BaseCampo, BaseAviso, MarcaDeconsta)
  router/            rutas y guardas de navegación
  assets/main.css    Tailwind y los tokens de la identidad (ciruela, rosa mineral, Manrope)
```

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
(`app.acceso.infraestructura.cli`) en la base de desarrollo. Cada ejecución hace unos 14 ingresos
desde la misma IP; el límite por defecto es de 20 por minuto, así que conviene esperar un minuto
entre ejecuciones seguidas.
