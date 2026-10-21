import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta } from '@/features/acceso/__tests__/respuestas'

import PorVerificarView from '../views/PorVerificarView.vue'

const MORA = {
  id: 'm1',
  deuda_id: 'd1',
  concepto: 'Luz de la casa',
  cuota: 1,
  importe: '14.40',
  importe_cuota: '182.40',
  nota: 'La empresa cobra mora desde el día siguiente.',
  estado: 'por_aprobar',
  confianza: 72,
  comprobaciones: [
    { codigo: 'mora', titulo: 'Mora', resultado: 'bien', detalle: 'La prueba muestra S/ 14.40.' },
  ],
  prueba_id: 'c2',
  declarada_por: 'Lucía Vega',
  declarada_en: '2026-10-21T10:00:00Z',
  decidida_en: null,
  motivo_decision: null,
}
const DETALLE = {
  ...MORA,
  prueba: {
    id: 'c2',
    deuda_id: 'd1',
    cuota: 1,
    estado: 'listo',
    tipo_archivo: 'image/png',
    nombre_archivo: 'recibo.png',
    tamano: 1000,
    subido_en: '2026-10-21T09:59:00Z',
    analizado_en: '2026-10-21T09:59:05Z',
    riesgo: 'bajo',
    senales: [],
    lectura: {
      lugar: null,
      medio: null,
      empresa: 'HIDRANDINA',
      numero_operacion: null,
      pagado_el: null,
      importe: '196.80',
      comision: null,
      mora: '14.40',
    },
    pago_id: null,
    proposito: 'mora',
    registro_bloqueado: false,
  },
}

function simularApi() {
  let decidida = false
  const mock = vi.fn<typeof fetch>((entrada, opciones) => {
    const ruta = new URL(String(entrada), 'http://localhost').pathname
    if (ruta.endsWith('/contenido')) return Promise.resolve(new Response(new Blob(['png'])))
    if (opciones?.method === 'POST') {
      decidida = true
      return Promise.resolve(respuesta(200, { ...DETALLE, estado: 'aprobada' }))
    }
    if (ruta.endsWith('/pagos/moras/m1')) return Promise.resolve(respuesta(200, DETALLE))
    // Decidida la mora, ya no espera aprobación.
    if (ruta.endsWith('/pagos/moras'))
      return Promise.resolve(respuesta(200, decidida ? [] : [MORA]))
    return Promise.resolve(respuesta(200, []))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

async function montar() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'por-verificar', component: PorVerificarView },
      { path: '/ingresar', name: 'inicio-sesion', component: { template: '<p />' } },
    ],
  })
  await router.push('/')
  const vista = mount(
    { template: '<RouterView />' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return vista
}

const boton = (vista: Awaited<ReturnType<typeof montar>>, texto: string) =>
  vista.findAll('button').find((b) => b.text().includes(texto))!

describe('Moras por aprobar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    URL.createObjectURL = vi.fn<typeof URL.createObjectURL>(() => 'blob:prueba')
    URL.revokeObjectURL = vi.fn<typeof URL.revokeObjectURL>()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('muestra la mora con su prueba y el gerente la aprueba', async () => {
    const api = simularApi()
    const vista = await montar()

    expect(vista.text()).toContain('Moras por aprobar · 1')
    expect(vista.text()).toContain('La empresa cobra mora desde el día siguiente.')
    await boton(vista, 'Aprobar la mora').trigger('click')
    await flushPromises()

    const envio = api.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(String(envio?.[0])).toContain('/pagos/moras/m1/aprobacion')
    expect(vista.text()).toContain('Aprobaste la mora de «Luz de la casa»')
  })

  it('rechazarla pide un motivo y lo envía al backend', async () => {
    const api = simularApi()
    const vista = await montar()

    await boton(vista, 'Rechazar').trigger('click')
    await vista.get('textarea').setValue('Esa mora no aplica.')
    await vista.get('dialog form').trigger('submit')
    await flushPromises()

    const envio = api.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(String(envio?.[0])).toContain('/pagos/moras/m1/rechazo')
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ motivo: 'Esa mora no aplica.' })
    expect(vista.text()).toContain('Rechazaste la mora de «Luz de la casa»')
  })
})
