import { expect, test } from '@playwright/test'

import { crearCuenta } from './cuentas'

test('el gerente define su límite y sus titulares autorizados, y los prueba', async ({ page }) => {
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
  await expect(page.getByText('Sin límite', { exact: true })).toBeVisible()

  // El límite se escribe como se lee en Perú y se guarda en soles exactos.
  const limite = page.getByLabel('Pedir autorización si el importe supera')
  await limite.pressSequentially('S/ 2,900')
  await expect(limite).toHaveValue('2,900')
  await expect(page.getByText(/Se guardará como S\/\s2,900\.00/)).toBeVisible()
  await page.getByRole('button', { name: 'Guardar límite' }).click()
  await expect(page.getByText(/Guardaste tu límite/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar límite' })).toBeDisabled()

  // Campos obligatorios vacíos: mensajes específicos y nada se envía.
  await page.getByRole('button', { name: 'Agregar titular' }).click()
  const ventana = page.getByRole('dialog', { name: 'Agregar un titular autorizado' })
  await ventana.getByRole('button', { name: 'Agregar titular' }).click()
  await expect(ventana.getByText('Escribe el nombre como aparece en sus recibos.')).toBeVisible()
  await expect(ventana.getByText(/Confirma que esta persona te autorizó/)).toBeVisible()

  await ventana.getByLabel('Nombre completo o razón social').fill('María de los Ángeles Ruiz Soto')
  await ventana.getByLabel('Relación contigo (opcional)').fill('Esposa')
  await ventana.getByRole('combobox', { name: /Documento/ }).selectOption('dni')
  await ventana.getByLabel('Número de DNI').pressSequentially('41a234568')
  await ventana.getByLabel(/Esta persona me autorizó/).check()
  await ventana.getByRole('button', { name: 'Agregar titular' }).click()
  await expect(page.getByText(/Agregaste a María de los Ángeles Ruiz Soto/)).toBeVisible()
  // El documento completo no vuelve al navegador.
  await expect(page.getByText('Esposa · DNI')).toBeVisible()
  await expect(page.getByText('41234568')).toHaveCount(0)

  // La prueba de reglas usa la misma evaluación que el registro de deudas.
  await page.getByLabel('Importe del documento').fill('3000')
  await page.getByLabel('Titular que figura (opcional)').fill('PEPITO PEREZ')
  await page.getByRole('button', { name: 'Probar' }).click()
  await expect(page.getByText('Esperaría tu autorización')).toBeVisible()
  await expect(page.getByText(/supera tu límite de S\/\s2,900\.00/)).toBeVisible()

  await page.getByLabel('Importe del documento').fill('500')
  await page.getByLabel('Titular que figura (opcional)').fill('RUIZ SOTO MARIA')
  await page.getByRole('button', { name: 'Probar' }).click()
  await expect(page.getByText('Entraría directo')).toBeVisible()
  await expect(page.getByText('Titular reconocido: Esposa.')).toBeVisible()

  // Las categorías son la otra pestaña de la misma página.
  await page.getByRole('link', { name: 'Categorías' }).click()
  await expect(page).toHaveURL(/\/configuracion\/categorias$/)
  await expect(page.getByRole('heading', { name: 'Un lugar para cada gasto.' })).toBeVisible()
})
