import { randomInt } from 'node:crypto'

import { expect, test, type Page } from '@playwright/test'

import { crearCuenta, type Cuenta } from './cuentas'

/** Ingresa por la API como gerente, acepta los documentos y abre Mi equipo. */
async function entrarComoGerente(page: Page): Promise<Cuenta> {
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
  await page.goto('/equipo')
  await page.getByRole('button', { name: 'Ahora no' }).click()
  return gerente
}

async function registrar(page: Page, dni: string) {
  await page.getByRole('link', { name: 'Registrar asistente' }).first().click()
  await expect(page).toHaveURL(/\/equipo\/nueva$/)
  await page.getByLabel('Nombres', { exact: true }).fill('Daniela')
  await page.getByLabel('Apellidos', { exact: true }).fill('Torres Ríos')
  await page.getByLabel('Celular').fill('987654321')
  await page.getByLabel('Número de DNI').fill(dni)
  await page.getByRole('button', { name: 'Crear cuenta de asistente' }).click()
}

async function leerCredenciales(page: Page) {
  const ventana = page.getByRole('dialog')
  const datos = ventana.locator('dd')
  return {
    usuario: (await datos.nth(0).textContent())!.trim(),
    contrasena: (await datos.nth(1).textContent())!.trim(),
  }
}

test('el gerente registra una asistente y ella completa su primer ingreso', async ({
  page,
  browser,
}) => {
  await entrarComoGerente(page)
  const dni = String(randomInt(10_000_000, 99_999_999))

  // Campos obligatorios vacíos: mensajes específicos y nada se envía.
  await page.getByRole('link', { name: 'Registrar asistente' }).first().click()
  await page.getByRole('button', { name: 'Crear cuenta de asistente' }).click()
  await expect(page.getByText('Escribe sus nombres.')).toBeVisible()
  await expect(page.getByText('Escribe su número de documento.')).toBeVisible()
  // Lo inválido no llega a escribirse.
  await page.getByLabel('Número de DNI').pressSequentially('12ab34')
  await expect(page.getByLabel('Número de DNI')).toHaveValue('1234')
  await expect(page.getByText('Faltan 4 dígitos.')).toBeVisible()
  await page.getByRole('link', { name: 'Cancelar' }).click()

  await registrar(page, dni)
  const ventana = page.getByRole('dialog', { name: 'Cuenta creada.' })
  await expect(ventana).toBeVisible()
  const credenciales = await leerCredenciales(page)
  expect(credenciales.usuario).toMatch(/^daniela\.torres\d*$/)
  await ventana.getByRole('button', { name: 'Listo' }).click()
  await expect(page.getByText('Daniela Torres Ríos ya es parte de tu equipo.')).toBeVisible()
  await expect(page.getByText('Primer ingreso pendiente').first()).toBeVisible()

  // La asistente ingresa: políticas, contraseña (la pospone) y datos (obligatorio).
  const asistente = await (await browser.newContext()).newPage()
  await asistente.goto('/ingresar')
  await asistente.getByLabel('Usuario', { exact: true }).fill(credenciales.usuario)
  await asistente.getByLabel('Contraseña', { exact: true }).fill(credenciales.contrasena)
  await asistente.getByRole('button', { name: 'Iniciar sesión' }).click()
  await asistente.getByLabel(/Acepto los términos de uso/).check()
  await asistente.getByLabel(/He leído la política de privacidad/).check()
  await asistente.getByRole('button', { name: 'Aceptar y entrar a mi espacio' }).click()
  await expect(
    asistente.getByRole('heading', { name: 'Crea tu contraseña personal.' }),
  ).toBeVisible()
  await asistente.getByRole('button', { name: 'Ahora no, lo haré después' }).click()
  await expect(asistente.getByRole('heading', { name: 'Confirma tus datos.' })).toBeVisible()
  // Mientras no confirme sus datos, no entra al espacio.
  await asistente.goto('/inicio')
  await expect(asistente).toHaveURL(/\/bienvenida$/)
  await asistente.getByLabel('Correo').fill(`dani.${dni}@ejemplo.pe`)
  await asistente.getByLabel(/Confirmo que estos datos son correctos/).check()
  await asistente.getByRole('button', { name: 'Confirmar mis datos' }).click()
  await expect(asistente).toHaveURL(/\/inicio$/)
  await expect(
    asistente.getByText('Estaremos disponibles pronto, con todo y mejoras.'),
  ).toBeVisible()
})

test('bloquear, eliminar y recuperar a una asistente', async ({ page }) => {
  await entrarComoGerente(page)
  const dni = String(randomInt(10_000_000, 99_999_999))
  await registrar(page, dni)
  const { usuario, contrasena } = await leerCredenciales(page)
  await page.getByRole('button', { name: 'Listo' }).click()

  await page.getByRole('button', { name: 'Bloquear' }).click()
  await page.getByLabel('Motivo (opcional)').fill('Vacaciones')
  await page.getByRole('button', { name: 'Bloquear cuenta' }).click()
  await expect(page.getByText(/Bloqueaste a Daniela Torres Ríos/)).toBeVisible()
  await expect(page.getByText('La bloqueaste tú.')).toBeVisible()

  // El bloqueo se aplica en el servidor: la asistente no ingresa y sabe por qué.
  const rechazo = await page.request.post('/api/v1/auth/login', {
    data: { nombre_usuario: usuario, contrasena },
    headers: { Cookie: '' },
  })
  expect(rechazo.status()).toBe(423)
  expect((await rechazo.json()).detail).toContain('Tu gerente bloqueó tu cuenta')

  await page.getByRole('button', { name: 'Desbloquear' }).click()
  await expect(page.getByText(/Desbloqueaste a Daniela Torres Ríos/)).toBeVisible()

  await page.getByRole('button', { name: 'Eliminar' }).click()
  await page.getByRole('button', { name: 'Eliminar cuenta' }).click()
  await expect(page.getByText('Aún no registras asistentes.')).toBeVisible()

  await registrar(page, dni)
  const eliminada = page.getByRole('dialog', { name: 'Ya registraste a esta persona antes.' })
  await expect(eliminada).toContainText(`@${usuario}`)
  await eliminada.getByRole('button', { name: /Recuperar su cuenta/ }).click()
  const recuperada = page.getByRole('dialog', { name: 'Cuenta recuperada.' })
  await expect(recuperada).toBeVisible()
  const nuevas = await leerCredenciales(page)
  expect(nuevas.usuario).toBe(usuario)
  expect(nuevas.contrasena).not.toBe(contrasena)
})

test('el gerente restablece la contraseña de una asistente que la olvidó', async ({ page }) => {
  await entrarComoGerente(page)
  await registrar(page, String(randomInt(10_000_000, 99_999_999)))
  const anteriores = await leerCredenciales(page)
  await page.getByRole('button', { name: 'Listo' }).click()

  await page.getByRole('button', { name: 'Restablecer contraseña' }).click()
  await page.getByLabel('Motivo (opcional)').fill('Olvidó su contraseña')
  await page.getByRole('dialog').getByRole('button', { name: 'Restablecer contraseña' }).click()

  const ventana = page.getByRole('dialog', { name: 'Contraseña restablecida.' })
  await expect(ventana).toBeVisible()
  const nuevas = await leerCredenciales(page)
  expect(nuevas.usuario).toBe(anteriores.usuario)
  expect(nuevas.contrasena).not.toBe(anteriores.contrasena)
  await ventana.getByRole('button', { name: 'Listo' }).click()
  await expect(page.getByText(/Restableciste la contraseña de Daniela Torres Ríos/)).toBeVisible()

  // La anterior ya no sirve (que la nueva funciona lo prueba el backend).
  const ingresar = (contrasena: string) =>
    page.request.post('/api/v1/auth/login', {
      data: { nombre_usuario: nuevas.usuario, contrasena },
      headers: { Cookie: '' },
    })
  expect((await ingresar(anteriores.contrasena)).status()).toBe(401)
})
