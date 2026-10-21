import { expect, test, type Page } from '@playwright/test'

import { crearCuenta, type Cuenta } from './cuentas'
import { reciboDeLuz } from './recibos'

/**
 * Requiere la API, el worker de la cola ocr (pnpm worker:ocr) y los servicios de compose. No
 * depende de la revisión con IA: con ella o sin ella (incompleta), el límite bajo del gerente hace
 * que la deuda espere su autorización.
 */
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

async function subir(page: Page, recibo: Buffer) {
  await page.locator('input[type="file"]').setInputFiles({
    name: 'recibo-luz.png',
    mimeType: 'image/png',
    buffer: recibo,
  })
  await expect(page.getByText('Lo que comprobamos')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Registrar deuda' })).toBeVisible({
    timeout: 90_000,
  })
}

test('la asistente registra una deuda y su gerente la autoriza en tiempo real', async ({
  browser,
}) => {
  test.setTimeout(120_000)
  const gerente = crearCuenta('gerente')
  const asistente = crearCuenta('asistente', gerente.usuario)
  const paginaGerente = await (await browser.newContext()).newPage()
  const paginaAsistente = await (await browser.newContext()).newPage()
  await entrar(paginaGerente, gerente, '/inicio')
  await paginaGerente.request.post('/api/v1/reglas/limite', { data: { limite_importe: '100.00' } })
  await entrar(paginaAsistente, asistente, '/registrar-deuda')

  const recibo = reciboDeLuz()
  await subir(paginaAsistente, recibo)

  // Campos obligatorios vacíos: el backend dice cuáles faltan.
  await paginaAsistente.getByLabel('Concepto').fill('')
  await paginaAsistente.getByRole('button', { name: 'Registrar deuda' }).click()
  await expect(paginaAsistente.getByText('Escribe un nombre para la deuda')).toBeVisible()

  await paginaAsistente.getByLabel('Concepto').fill('Luz de la casa · setiembre')
  await paginaAsistente.getByLabel('Importe (S/)').fill('182.40')
  await paginaAsistente.getByLabel('Vence el').fill('2026-12-28')
  await paginaAsistente.getByText('Agente o agencia').click()
  await paginaAsistente.getByRole('button', { name: 'Registrar deuda' }).click()
  await expect(
    paginaAsistente.getByRole('heading', { name: 'Se envió a tu gerente.' }),
  ).toBeVisible()

  // Al gerente le llega el aviso sin recargar y decide desde «Por autorizar».
  await expect(
    paginaGerente.getByRole('link', { name: /Notificaciones, 1 sin leer/ }),
  ).toBeVisible()
  await expect(paginaGerente.getByText('Una deuda espera tu autorización')).toBeVisible()
  await paginaGerente.getByRole('link', { name: 'Por autorizar' }).click()
  await expect(
    paginaGerente.getByRole('heading', { name: 'Luz de la casa · setiembre' }),
  ).toBeVisible()
  await paginaGerente.getByRole('button', { name: 'Autorizar deuda' }).click()
  await expect(paginaGerente.getByText('Autorizaste «Luz de la casa · setiembre».')).toBeVisible()
  await expect(paginaGerente.getByText('Todas tus decisiones están al día.')).toBeVisible()

  // El mismo recibo no respalda otra deuda.
  await paginaAsistente.getByRole('button', { name: 'Registrar otra deuda' }).click()
  await paginaAsistente.locator('input[type="file"]').setInputFiles({
    name: 'otra-vez.png',
    mimeType: 'image/png',
    buffer: recibo,
  })
  const repetido = paginaAsistente.getByRole('dialog', { name: 'Este documento ya lo usaste.' })
  await expect(repetido.getByText('Luz de la casa · setiembre')).toBeVisible()
})
