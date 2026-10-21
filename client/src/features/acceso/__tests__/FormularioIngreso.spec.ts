import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import FormularioIngreso from '../components/FormularioIngreso.vue'
import { respuesta, SESION, simularFetch } from './respuestas'

function montar() {
  return mount(FormularioIngreso, { attachTo: document.body })
}

async function completar(formulario: ReturnType<typeof montar>, usuario = 'lucia.vega') {
  await formulario.find('input[autocomplete="username"]').setValue(usuario)
  await formulario.find('input[autocomplete="current-password"]').setValue('Secreta-2026')
}

describe('FormularioIngreso', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('indica cada campo obligatorio sin llamar a la API', async () => {
    const fetch = simularFetch()
    const formulario = montar()

    await formulario.find('form').trigger('submit')

    expect(formulario.text()).toContain('Ingresa tu nombre de usuario.')
    expect(formulario.text()).toContain('Ingresa tu contraseña.')
    expect(fetch).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(formulario.find('input[autocomplete="username"]').element)
  })

  it('bloquea el botón mientras envía, ignora otro envío y lo recupera tras un error', async () => {
    let responder!: (r: Response) => void
    const fetch = simularFetch(new Promise<Response>((r) => (responder = r)))
    const formulario = montar()
    await completar(formulario)

    await formulario.find('form').trigger('submit')
    const boton = formulario.find('button[type="submit"]')
    expect(boton.attributes('disabled')).toBeDefined()
    expect(boton.attributes('aria-busy')).toBe('true')
    expect(boton.text()).toContain('Ingresando…')

    await formulario.find('form').trigger('submit')
    expect(fetch).toHaveBeenCalledTimes(1)

    responder(
      respuesta(401, {
        code: 'CREDENCIALES_INCORRECTAS',
        detail: 'Usuario o contraseña incorrectos.',
      }),
    )
    await flushPromises()

    expect(boton.attributes('disabled')).toBeUndefined()
    expect(boton.text()).toContain('Iniciar sesión')
    expect(formulario.get('[role="alert"]').text()).toContain('Usuario o contraseña incorrectos.')
    expect(
      (formulario.find('input[autocomplete="current-password"]').element as HTMLInputElement).value,
    ).toBe('')
  })

  it('explica que la cuenta está bloqueada y que debe intervenir el gerente', async () => {
    simularFetch(
      respuesta(423, {
        code: 'CUENTA_BLOQUEADA',
        detail: 'Tu cuenta está bloqueada. Pide a tu gerente que la desbloquee.',
      }),
    )
    const formulario = montar()
    await completar(formulario)

    await formulario.find('form').trigger('submit')
    await flushPromises()

    expect(formulario.text()).toContain('Cuenta bloqueada')
    expect(formulario.text()).toContain('Pide a tu gerente que la desbloquee.')
  })

  it('espera el tiempo de Retry-After antes de permitir otro intento', async () => {
    simularFetch(
      respuesta(429, {
        code: 'DEMASIADAS_SOLICITUDES',
        detail: 'Espera 30 segundos.',
        retry_after: 30,
      }),
    )
    const formulario = montar()
    await completar(formulario)

    await formulario.find('form').trigger('submit')
    await flushPromises()

    const boton = formulario.find('button[type="submit"]')
    expect(boton.text()).toContain('Espera 0:30')
    expect(boton.attributes('disabled')).toBeDefined()
  })

  it('avisa si no hay conexión con la API', async () => {
    simularFetch(Promise.reject(new TypeError('Failed to fetch')))
    const formulario = montar()
    await completar(formulario)

    await formulario.find('form').trigger('submit')
    await flushPromises()

    expect(formulario.get('[role="alert"]').text()).toContain('No pudimos conectar con Deconsta.')
  })

  it('envía las credenciales y emite el ingreso', async () => {
    const fetch = simularFetch(respuesta(200, { ...SESION, primer_ingreso: true }))
    const formulario = montar()
    await completar(formulario)

    await formulario.find('form').trigger('submit')
    await flushPromises()

    const [ruta, opciones] = fetch.mock.calls[0] as [string, RequestInit]
    expect(ruta).toBe('/api/v1/auth/login')
    expect(JSON.parse(String(opciones.body))).toEqual({
      nombre_usuario: 'lucia.vega',
      contrasena: 'Secreta-2026',
    })
    expect(formulario.emitted('ingreso')?.[0]).toEqual([{ ...SESION, primer_ingreso: true }])
  })
})
