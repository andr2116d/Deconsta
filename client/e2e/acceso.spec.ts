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

test('primer ingreso: omitir recuerda el cambio y cambiarla lo apaga', async ({ page }) => {
  const gerente = crearCuenta('gerente')

  await ingresar(page, gerente.usuario, gerente.contrasena)
  await expect(page.getByRole('heading', { name: 'Crea tu contraseña personal.' })).toBeVisible()
  await page.getByRole('button', { name: 'Omitir por ahora' }).click()
  await expect(page.getByRole('heading', { name: 'Estaremos disponibles pronto.' })).toBeVisible()
  await expect(page.getByText('Contraseña temporal', { exact: true })).toBeVisible()

  // Recargar conserva la sesión: la cookie la valida el backend.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Estaremos disponibles pronto.' })).toBeVisible()

  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await ingresar(page, gerente.usuario, gerente.contrasena)
  await expect(page).toHaveURL(/\/cambiar-contrasena$/)

  await page.getByLabel('Contraseña temporal', { exact: true }).fill(gerente.contrasena)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(NUEVA)
  await expect(page.getByRole('meter')).toHaveAttribute('aria-valuetext', 'Muy segura')
  await page.getByLabel('Repite la nueva contraseña', { exact: true }).fill(NUEVA)
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()
  await expect(page.getByText('Contraseña actualizada.')).toBeVisible()
  await expect(page.getByText('Contraseña temporal', { exact: true })).toBeHidden()

  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await ingresar(page, gerente.usuario, NUEVA)
  await expect(page).toHaveURL(/\/inicio$/)
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
  const desbloqueo = await request.post(`/api/v1/asistentes/${asistente.id}/desbloqueo`, {
    data: { motivo: 'Prueba automatizada' },
  })
  expect(desbloqueo.ok()).toBe(true)

  await ingresar(page, asistente.usuario, asistente.contrasena)
  await expect(page).toHaveURL(/\/cambiar-contrasena$/)
})
