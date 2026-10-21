import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import RegistrarDeudaView from '../views/RegistrarDeudaView.vue'

const SUBIDO = {
  id: 'd1',
  estado: 'analizando',
  tipo_archivo: 'image/png',
  nombre_archivo: 'recibo.png',
  tamano: 1000,
  paginas: 1,
  subido_en: '2026-10-21T10:00:00Z',
  analizado_en: null,
  riesgo: null,
  senales: [],
  propuesta: null,
  repetido_de: null,
  deuda_id: null,
}

function montar() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: { template: '<p />' } },
      { path: '/ingresar', name: 'inicio-sesion', component: { template: '<p />' } },
    ],
  })
  return mount(RegistrarDeudaView, { global: { plugins: [router] }, attachTo: document.body })
}

async function elegir(vista: ReturnType<typeof montar>, tipo = 'image/png') {
  const archivo = new File([new Uint8Array([137, 80, 78, 71])], 'recibo.png', { type: tipo })
  const entrada = vista.get('input[type="file"]')
  Object.defineProperty(entrada.element, 'files', { value: [archivo] })
  await entrada.trigger('change')
  await flushPromises()
}

describe('RegistrarDeudaView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    URL.createObjectURL = vi.fn(() => 'blob:vista')
    URL.revokeObjectURL = vi.fn()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('un documento ilegible no deja llenar los datos', async () => {
    simularFetch(
      respuesta(200, []),
      respuesta(202, SUBIDO),
      respuesta(200, {
        ...SUBIDO,
        estado: 'ilegible',
        riesgo: 'alto',
        senales: [
          { capa: 'lectura', codigo: 'DOCUMENTO_ILEGIBLE', detalle: 'No se lee.', riesgo: 'alto' },
        ],
      }),
    )
    const vista = montar()
    await flushPromises()

    await elegir(vista)
    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()

    expect(vista.text()).toContain('No se puede leer el documento')
    expect(vista.find('form').exists()).toBe(false)
  })

  it('un documento ya usado dice en qué deuda y si se pausó el registro', async () => {
    simularFetch(
      respuesta(200, []),
      respuesta(409, {
        code: 'DOCUMENTO_YA_REGISTRADO',
        detail: 'Este documento ya se usó en la deuda «Luz de la casa».',
        existing_debt: {
          id: 'x',
          concepto: 'Luz de la casa',
          registrada_en: '2026-10-20T15:00:00Z',
        },
        registration_blocked: true,
      }),
    )
    const vista = montar()
    await flushPromises()

    await elegir(vista)

    expect(document.body.textContent).toContain('Este documento ya lo usaste.')
    expect(document.body.textContent).toContain('Luz de la casa')
    expect(document.body.textContent).toContain('Registro de deudas en pausa')
  })

  it('un corte de red mientras se analiza no pierde el documento', async () => {
    const fetch = simularFetch(respuesta(200, []), respuesta(202, SUBIDO))
    fetch.mockImplementationOnce(() => Promise.reject(new TypeError('Failed to fetch')))
    fetch.mockImplementationOnce(() =>
      Promise.resolve(respuesta(503, { code: 'SERVICIO_NO_DISPONIBLE', detail: 'No disponible.' })),
    )
    fetch.mockImplementationOnce(() =>
      Promise.resolve(respuesta(200, { ...SUBIDO, estado: 'listo', riesgo: 'bajo' })),
    )
    const vista = montar()
    await flushPromises()

    await elegir(vista)
    await vi.advanceTimersByTimeAsync(4000)
    await flushPromises()

    expect(vista.text()).not.toContain('No pudimos usar este documento')
    expect(vista.find('form').exists()).toBe(true)
  })

  it('avisa cuando el análisis tarda más de lo habitual', async () => {
    const analizando = Array.from({ length: 20 }, () => respuesta(200, SUBIDO))
    simularFetch(respuesta(200, []), respuesta(202, SUBIDO), ...analizando)
    const vista = montar()
    await flushPromises()

    await elegir(vista)
    expect(vista.text()).not.toContain('Está tardando un poco más')
    await vi.advanceTimersByTimeAsync(21_000)
    await flushPromises()

    expect(vista.text()).toContain('Está tardando un poco más')
  })

  it('rechaza en el navegador lo que no es una imagen ni un PDF, sin subirlo', async () => {
    const fetch = simularFetch(respuesta(200, []))
    const vista = montar()
    await flushPromises()

    await elegir(vista, 'application/zip')

    expect(vista.text()).toContain('Sube una imagen JPG, PNG o WebP, o un PDF del documento.')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
