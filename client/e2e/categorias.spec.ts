import { expect, test, type Page } from '@playwright/test'

import { crearCuenta } from './cuentas'

/** Ingresa por la API como un gerente nuevo, acepta los documentos y abre sus categorías. */
async function entrarComoGerente(page: Page) {
  const gerente = crearCuenta('gerente')
  const ingreso = await page.request.post('/api/v1/auth/login', {
    data: { nombre_usuario: gerente.usuario, contrasena: gerente.contrasena },
  })
  expect(ingreso.ok()).toBe(true)
  const vigentes: Array<{ tipo: string; version: number }> = await (
    await page.request.get('/api/v1/documentos-legales')
  ).json()
  await page.request.post('/api/v1/documentos-legales/aceptacion', {
    data: { documentos: vigentes.map(({ tipo, version }) => ({ tipo, version })) },
  })
  await page.goto('/configuracion')
  await page.getByRole('button', { name: 'Ahora no' }).click()
}

test('el gerente crea, edita, archiva y reactiva categorías', async ({ page }) => {
  await entrarComoGerente(page)
  await expect(page.getByText('Aún no tienes categorías.')).toBeVisible()

  // Nombre vacío: mensaje específico y nada se envía.
  await page.getByRole('button', { name: 'Nueva categoría' }).click()
  const ventana = page.getByRole('dialog', { name: 'Nueva categoría' })
  await ventana.getByRole('button', { name: 'Crear categoría' }).click()
  await expect(ventana.getByText('Escribe el nombre de la categoría.')).toBeVisible()

  // Lo inválido no llega a escribirse y el nombre propio se crea con su color e ícono.
  await ventana.getByLabel('Nombre', { exact: true }).pressSequentially('Tarjeta <Visa>')
  await expect(ventana.getByLabel('Nombre', { exact: true })).toHaveValue('Tarjeta Visa')
  await ventana.getByTitle('Ciruela').click()
  await ventana.getByTitle('Tarjeta', { exact: true }).click()
  await expect(ventana.getByLabel('Tarjeta', { exact: true })).toBeChecked()
  await ventana.getByRole('button', { name: 'Crear categoría' }).click()
  await expect(page.getByText('Creaste la categoría «Tarjeta Visa».')).toBeVisible()

  // Una sugerencia se revisa antes de crearla.
  await page.getByRole('button', { name: 'Agua', exact: true }).click()
  await expect(page.getByRole('dialog').getByLabel('Nombre', { exact: true })).toHaveValue('Agua')
  await page.getByRole('button', { name: 'Crear categoría' }).click()
  const lista = page.getByRole('list', { name: 'Categorías activas' })
  await expect(lista.getByRole('heading')).toHaveText(['Agua', 'Tarjeta Visa'])

  // Un nombre repetido se avisa al escribir y el backend lo rechaza.
  await page.getByRole('button', { name: 'Nueva categoría' }).click()
  await page.getByRole('dialog').getByLabel('Nombre', { exact: true }).fill('AGUA')
  await expect(page.getByText('Ya tienes una categoría llamada «Agua».')).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar' }).click()

  // Editar solo guarda cambios reales.
  await page.getByRole('button', { name: 'Editar Agua' }).click()
  const edicion = page.getByRole('dialog', { name: 'Editar categoría' })
  await expect(edicion.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
  await edicion.getByLabel('Nombre', { exact: true }).fill('Agua y desagüe')
  await edicion.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('Guardaste los cambios de «Agua y desagüe».')).toBeVisible()

  // Archivar la retira de las activas; reactivarla la devuelve.
  await page.getByRole('button', { name: 'Archivar Tarjeta Visa' }).click()
  await page.getByLabel('Motivo (opcional)').fill('Cerré la tarjeta')
  await page.getByRole('button', { name: 'Archivar categoría' }).click()
  await expect(lista.getByRole('heading')).toHaveText(['Agua y desagüe'])
  await page.getByRole('button', { name: /Archivadas/ }).click()
  await page.getByRole('button', { name: 'Reactivar Tarjeta Visa' }).click()
  await expect(page.getByText('Reactivaste «Tarjeta Visa».', { exact: false })).toBeVisible()
  await expect(lista.getByRole('heading')).toHaveText(['Agua y desagüe', 'Tarjeta Visa'])
})
