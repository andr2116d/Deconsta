import { expect, test, type Page } from '@playwright/test'

import { crearCuenta, type Cuenta } from './cuentas'

/** Ingresa por la API (las cookies son las mismas de la página) y acepta los documentos. */
async function entrar(page: Page, cuenta: Cuenta, ruta: string) {
  const ingreso = await page.request.post('/api/v1/auth/login', {
    data: { nombre_usuario: cuenta.usuario, contrasena: cuenta.contrasena },
  })
  expect(ingreso.ok()).toBe(true)
  const vigentes: Array<{ tipo: string; version: number }> = await (
    await page.request.get('/api/v1/documentos-legales')
  ).json()
  await page.request.post('/api/v1/documentos-legales/aceptacion', {
    data: { documentos: vigentes.map(({ tipo, version }) => ({ tipo, version })) },
  })
  await page.goto(ruta)
  await page.getByRole('button', { name: 'Ahora no' }).click()
}

test('el gerente actualiza sus datos y la cabecera lo refleja sin recargar', async ({ page }) => {
  const gerente = crearCuenta('gerente')
  await entrar(page, gerente, '/cuenta')

  await expect(
    page.getByRole('heading', { level: 1, name: 'Tu cuenta, a tu nombre.' }),
  ).toBeVisible()
  const pestanas = page.getByRole('navigation', { name: 'Secciones de Mi cuenta' })
  await expect(pestanas.getByRole('link')).toHaveText([
    'Mis datos',
    'Usuario y contraseña',
    'Mi rol y permisos',
    'Privacidad',
  ])
  await expect(page.getByLabel('Cargo')).toHaveValue('Sin cargo asignado')
  await expect(page.getByLabel('Cargo')).not.toBeEditable()

  // Un espacio de más no es un cambio real.
  const guardar = page.getByRole('button', { name: 'Guardar mis datos' })
  const nombres = page.getByLabel('Nombres', { exact: true })
  await expect(guardar).toBeDisabled()
  await nombres.fill('Prueba ')
  await expect(guardar).toBeDisabled()

  // El número de DNI no se cambia: se advierte antes de guardar.
  const numero = page.getByLabel('Número de DNI')
  const dni = await numero.inputValue()
  await numero.fill('12345678')
  await expect(page.getByText('no se puede cambiar.').first()).toBeVisible()
  await expect(guardar).toBeDisabled()
  await numero.fill(dni)

  await nombres.fill('Prueba Renombrada')
  await page.getByLabel('Nombre como figura en tus recibos').fill('Automatizada, Prueba')
  await expect(guardar).toBeEnabled()
  await guardar.click()

  await expect(page.getByText('Tus datos se guardaron.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Tu cuenta/ })).toContainText('Prueba Renombrada')
  await expect(page.getByRole('complementary', { name: 'Resumen de tu cuenta' })).toContainText(
    'Prueba Renombrada Automatizada',
  )
  await expect(guardar).toBeDisabled()
})

test('si falla el guardado, una ventana explica qué pasó y permite reintentar', async ({
  page,
}) => {
  await entrar(page, crearCuenta('gerente'), '/cuenta')
  await page.route('/api/v1/cuenta/datos', (ruta) =>
    ruta.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ code: 'SERVICIO_NO_DISPONIBLE', detail: 'El servicio no responde.' }),
    }),
  )

  await page.getByLabel('Celular').fill('912345678')
  await page.getByRole('button', { name: 'Guardar mis datos' }).click()

  const ventana = page.getByRole('dialog', { name: 'No pudimos guardar tus datos' })
  await expect(ventana).toBeVisible()
  await expect(ventana).toContainText('El servicio no responde.')
  await page.unroute('/api/v1/cuenta/datos')
  await ventana.getByRole('button', { name: 'Reintentar' }).click()
  await expect(ventana).toBeHidden()
  await expect(page.getByText('Tus datos se guardaron.')).toBeVisible()
})

test('cambia el usuario con su contraseña y descuenta el cupo del mes', async ({ page }) => {
  const asistente = crearCuenta('asistente', crearCuenta('gerente').usuario)
  await entrar(page, asistente, '/cuenta/acceso')

  // La asistente no tiene nombre en recibos.
  await page.getByRole('link', { name: 'Mis datos' }).click()
  await expect(page.getByLabel('Celular')).toBeVisible()
  await expect(page.getByLabel('Nombre como figura en tus recibos')).toHaveCount(0)
  await page.getByRole('link', { name: 'Usuario y contraseña' }).click()

  await expect(page.getByText('Te quedan 3 cambios de usuario este mes.')).toBeVisible()
  const nuevo = `${asistente.usuario}.b`
  await page.getByRole('textbox', { name: 'Usuario de acceso' }).fill(nuevo.toUpperCase())
  await expect(page.getByText(`Quedará como @${nuevo}.`)).toBeVisible()
  await page.getByLabel('Contraseña actual', { exact: true }).fill(asistente.contrasena)
  await page.getByRole('button', { name: 'Cambiar usuario' }).click()

  await expect(page.getByText(`Tu usuario ahora es @${nuevo}.`)).toBeVisible()
  await expect(page.getByText('Te quedan 2 cambios de usuario este mes.')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Resumen de tu cuenta' })).toContainText(
    `@${nuevo}`,
  )

  // La nueva contraseña igual a la actual se advierte antes de enviar.
  await page.getByLabel('Contraseña temporal', { exact: true }).fill(asistente.contrasena)
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(asistente.contrasena)
  await expect(page.getByText('La nueva contraseña debe ser distinta de la actual.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar contraseña' })).toBeDisabled()
})

test('rol, permisos y privacidad son pestañas de la misma página', async ({ page }) => {
  await entrar(page, crearCuenta('gerente'), '/cuenta/permisos')

  await expect(page.getByRole('table', { name: 'Qué puede hacer cada rol' })).toBeVisible()
  await page.getByRole('link', { name: 'Privacidad', exact: true }).click()
  await expect(page).toHaveURL(/\/cuenta\/privacidad$/)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Tu cuenta, a tu nombre.' }),
  ).toBeVisible()
  await expect(page.getByText(/Versión 1 · aceptada el/)).toHaveCount(2)
})
