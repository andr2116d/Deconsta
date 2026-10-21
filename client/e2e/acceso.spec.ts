import { expect, test, type Page } from '@playwright/test'

import { crearCuenta } from './cuentas'

const NUEVA = 'Ciruela-Rosa-2026'

async function ingresar(page: Page, usuario: string, contrasena: string) {
  await page.goto('/ingresar')
  await page.getByLabel('Usuario', { exact: true }).fill(usuario)
  await page.getByLabel('Contraseña', { exact: true }).fill(contrasena)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
}

test('valida los campos y rechaza credenciales incorrectas', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/ingresar$/)

  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Ingresa tu nombre de usuario.')).toBeVisible()
  await expect(page.getByText('Ingresa tu contraseña.')).toBeVisible()

  await ingresar(page, 'usuario.que.no.existe', 'Cualquiera-2026')
  await expect(page.getByRole('alert')).toContainText('Usuario o contraseña incorrectos.')
})

async function cambiarContrasena(page: Page, temporal: string, nueva: string) {
  const modal = page.getByRole('dialog', { name: 'Crea tu contraseña personal.' })
  await modal.getByLabel('Contraseña temporal', { exact: true }).fill(temporal)
  await modal.getByLabel('Nueva contraseña', { exact: true }).fill(nueva)
  await modal.getByLabel('Repite la nueva contraseña', { exact: true }).fill(nueva)
  await modal.getByRole('button', { name: 'Guardar contraseña' }).click()
}

test('primer ingreso: contraseña obligatoria, aceptación y próxima disponibilidad', async ({
  page,
}) => {
  const gerente = crearCuenta('gerente')

  await ingresar(page, gerente.usuario, gerente.contrasena)
  await expect(page).toHaveURL(/\/bienvenida$/)
  const modal = page.getByRole('dialog', { name: 'Crea tu contraseña personal.' })
  await expect(modal).toBeVisible()
  await expect(modal.getByRole('button', { name: 'Omitir por ahora' })).toHaveCount(0)

  // Escape no cierra la ventana y la navegación directa no salta el paso.
  await page.keyboard.press('Escape')
  await expect(modal).toBeVisible()
  await page.goto('/inicio')
  await expect(page).toHaveURL(/\/bienvenida$/)
  expect((await page.request.get('/api/v1/espacio')).status()).toBe(403)

  // Un cambio fallido no avanza.
  await cambiarContrasena(page, 'Equivocada-2026', NUEVA)
  await expect(modal.getByText('La contraseña actual no es correcta.')).toBeVisible()
  await modal.getByLabel('Nueva contraseña', { exact: true }).fill('corta')
  await expect(modal.getByRole('meter')).not.toHaveAttribute('aria-valuetext', 'Muy segura')

  await cambiarContrasena(page, gerente.contrasena, NUEVA)
  await expect(modal).toBeHidden()
  await expect(page.getByText('Contraseña actualizada. Último paso')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Antes de empezar, tus datos.' })).toBeVisible()

  // Leer no acepta: el documento se abre y se cierra sin marcar la casilla.
  await page.getByRole('button', { name: 'Leer los términos de uso' }).click()
  const lector = page.getByRole('dialog', { name: 'Términos de uso' })
  await expect(lector.getByText('Versión 1 · vigente desde')).toBeVisible()
  await lector.getByRole('button', { name: 'Cerrar', exact: true }).last().click()
  await expect(lector).toBeHidden()
  await page.getByRole('button', { name: 'Aceptar y entrar a mi espacio' }).click()
  await expect(page.getByText('Marca las dos casillas para continuar.')).toBeVisible()

  // Recargar conserva el paso: lo decide el backend.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Antes de empezar, tus datos.' })).toBeVisible()
  await page.goto('/inicio')
  await expect(page).toHaveURL(/\/bienvenida$/)

  await page.getByLabel(/Acepto los términos de uso/).check()
  await page.getByLabel(/He leído la política de privacidad/).check()
  await page.getByRole('button', { name: 'Aceptar y entrar a mi espacio' }).click()
  await expect(page).toHaveURL(/\/inicio$/)
  await expect(page.getByRole('heading', { name: 'Estaremos disponibles pronto.' })).toBeVisible()
  await expect(page.getByText('Todo listo.')).toBeVisible()

  await page.goto('/bienvenida')
  await expect(page).toHaveURL(/\/inicio$/)

  // El siguiente ingreso entra directo: no se vuelve a pedir nada.
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await ingresar(page, gerente.usuario, NUEVA)
  await expect(page).toHaveURL(/\/inicio$/)
  await expect(page.getByRole('heading', { name: 'Estaremos disponibles pronto.' })).toBeVisible()
})

test('la asistente ve su paso de privacidad con el acento de su rol', async ({ page }) => {
  const gerente = crearCuenta('gerente')
  const asistente = crearCuenta('asistente', gerente.usuario)

  await ingresar(page, asistente.usuario, asistente.contrasena)
  await cambiarContrasena(page, asistente.contrasena, NUEVA)
  await expect(page.locator('html')).toHaveAttribute('data-rol', 'asistente')
  await expect(page.locator('small', { hasText: 'Asistente' })).toBeVisible()
  const boton = page.getByRole('button', { name: 'Aceptar y entrar a mi espacio' })
  await expect(boton).toHaveCSS('background-color', 'rgb(54, 92, 75)')

  // Cerrar sesión a mitad del flujo no da nada por aceptado.
  await page.getByRole('button', { name: 'Salir de la sesión' }).click()
  await ingresar(page, asistente.usuario, NUEVA)
  await expect(page.getByRole('heading', { name: 'Antes de empezar, tus datos.' })).toBeVisible()
})

test('la asistente queda bloqueada al quinto intento hasta que su gerente la desbloquea', async ({
  page,
  request,
}) => {
  const gerente = crearCuenta('gerente')
  const asistente = crearCuenta('asistente', gerente.usuario)

  for (let intento = 1; intento <= 4; intento++) {
    await ingresar(page, asistente.usuario, `Equivocada-${intento}`)
    await expect(page.getByRole('alert')).toContainText('Usuario o contraseña incorrectos.')
  }
  await ingresar(page, asistente.usuario, 'Equivocada-5')
  await expect(page.getByRole('status')).toContainText('Cuenta bloqueada')
  await expect(page.getByRole('status')).toContainText('Pide a tu gerente')

  // La contraseña correcta tampoco entra, aunque se recargue la página.
  await page.reload()
  await ingresar(page, asistente.usuario, asistente.contrasena)
  await expect(page.getByRole('status')).toContainText('Cuenta bloqueada')

  // El gerente la desbloquea por la API (la pantalla de equipo llegará en otra tarea).
  const ingresoGerente = await request.post('/api/v1/auth/login', {
    data: { nombre_usuario: gerente.usuario, contrasena: gerente.contrasena },
  })
  expect(ingresoGerente.ok()).toBe(true)
  // Sin completar su primer ingreso, el gerente tampoco puede desbloquear.
  const retenido = await request.post(`/api/v1/asistentes/${asistente.id}/desbloqueo`)
  expect((await retenido.json()).code).toBe('INCORPORACION_PENDIENTE')
  await request.post('/api/v1/auth/contrasena', {
    data: { contrasena_actual: gerente.contrasena, contrasena_nueva: NUEVA },
  })
  const vigentes: Array<{ tipo: string; version: number }> = await (
    await request.get('/api/v1/documentos-legales')
  ).json()
  await request.post('/api/v1/documentos-legales/aceptacion', {
    data: { documentos: vigentes.map(({ tipo, version }) => ({ tipo, version })) },
  })
  const desbloqueo = await request.post(`/api/v1/asistentes/${asistente.id}/desbloqueo`, {
    data: { motivo: 'Prueba automatizada' },
  })
  expect(desbloqueo.ok()).toBe(true)

  await ingresar(page, asistente.usuario, asistente.contrasena)
  await expect(page).toHaveURL(/\/bienvenida$/)
})
