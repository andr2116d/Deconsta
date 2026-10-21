import { expect, test, type Page } from '@playwright/test'

import { crearCuenta } from './cuentas'

/** Ingresa por la API (las cookies son las mismas de la página) y acepta los documentos. */
async function entrarAlEspacio(page: Page) {
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
  await page.goto('/inicio')
  await page.getByRole('button', { name: 'Ahora no' }).click()
  return gerente
}

test('gerencia recorre sus pestañas y cada sección dice que está en desarrollo', async ({
  page,
}) => {
  await entrarAlEspacio(page)
  const pestanas = page.getByRole('navigation', { name: 'Secciones de gerencia' })

  await expect(pestanas.getByRole('link')).toHaveText([
    'Resumen',
    'Por autorizar',
    'Por verificar',
    'Calendario',
    'Historial',
    'Mi equipo',
  ])
  await pestanas.getByRole('link', { name: 'Por verificar' }).click()
  await expect(page).toHaveURL(/\/por-verificar$/)
  await expect(page).toHaveTitle('Por verificar · Deconsta')
  await expect(page.getByRole('heading', { level: 1, name: 'Por verificar' })).toBeFocused()
  await expect(page.getByText('Esta funcionalidad está en desarrollo.')).toBeVisible()

  await page.getByRole('link', { name: 'Registrar deuda' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Registrar deuda' })).toBeVisible()

  // La tarjeta de la cuenta lleva a las secciones de la cuenta y se cierra al navegar.
  await page.getByRole('button', { name: /Tu cuenta/ }).click()
  await page.getByRole('link', { name: 'Límites y categorías' }).click()
  await expect(page).toHaveURL(/\/configuracion$/)
  await expect(page.getByRole('link', { name: 'Mi rol y permisos' })).toBeHidden()
})

const ANCHOS = [
  { nombre: 'móvil pequeño', width: 320, height: 640 },
  { nombre: 'móvil', width: 390, height: 844 },
  { nombre: 'tableta', width: 768, height: 1024 },
  { nombre: 'portátil', width: 1280, height: 800 },
  { nombre: 'escritorio', width: 1920, height: 1080 },
  { nombre: 'muy grande', width: 2560, height: 1440 },
]

test('el espacio se adapta sin desplazamiento horizontal de la página', async ({ page }) => {
  await entrarAlEspacio(page)
  const menu = page.getByRole('button', { name: /Tu cuenta/ })

  for (const ancho of ANCHOS) {
    await test.step(ancho.nombre, async () => {
      await page.setViewportSize({ width: ancho.width, height: ancho.height })
      await page.goto('/historial')

      const desborde = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      )
      expect(desborde).toBe(0)
      await expect(page.getByRole('link', { name: 'Registrar deuda' })).toBeVisible()
      // La pestaña activa queda a la vista aunque las pestañas se desplacen de lado.
      await expect(page.getByRole('link', { name: 'Historial' })).toBeInViewport()

      await menu.click()
      const panel = page.locator(`#${await menu.getAttribute('aria-controls')}`)
      await expect(panel).toBeVisible()
      const caja = await panel.boundingBox()
      expect(caja!.x).toBeGreaterThanOrEqual(0)
      expect(caja!.x + caja!.width).toBeLessThanOrEqual(ancho.width)
      await page.keyboard.press('Escape')
      await expect(panel).toBeHidden()
    })
  }
})
