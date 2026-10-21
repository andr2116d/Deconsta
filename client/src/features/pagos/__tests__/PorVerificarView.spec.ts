import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta } from '@/features/acceso/__tests__/respuestas'

import PorVerificarView from '../views/PorVerificarView.vue'

const PAGO = {
  id: 'p1',
  deuda_id: 'd1',
  concepto: 'Luz de la casa',
  cuota: 1,
  importe: '182.40',
  comision: '1.00',
  lugar_pago: 'agente',
  pagado_el: '2026-10-21',
  estado: 'por_verificar',
  confianza: 64,
  comprobaciones: [
    { codigo: 'importe', titulo: 'Importe', resultado: 'bien', detalle: 'Coincide con la cuota.' },
    {
      codigo: 'empresa',
      titulo: 'Empresa',
      resultado: 'aviso',
      detalle: 'La empresa pagada no parece la del documento.',
    },
  ],
  comprobantes: ['c1'],
  registrado_por: 'Lucía Vega',
  registrado_en: '2026-10-21T10:01:00Z',
  decidido_en: null,
  motivo_decision: null,
}
const DETALLE = {
  ...PAGO,
  cuotas: 1,
  detalle_comprobantes: [
    {
      id: 'c1',
      deuda_id: 'd1',
      cuota: 1,
      estado: 'listo',
      tipo_archivo: 'image/png',
      nombre_archivo: 'voucher.png',
      tamano: 1000,
      subido_en: '2026-10-21T10:00:00Z',
      analizado_en: '2026-10-21T10:00:05Z',
      riesgo: 'medio',
      senales: [],
      lectura: {
        lugar: 'agente',
        medio: 'Agente BCP',
        empresa: 'MOVISTAR',
        numero_operacion: '0458213',
        pagado_el: '2026-10-21',
        importe: '182.40',
        comision: '1.00',
      },
      pago_id: 'p1',
      registro_bloqueado: false,
    },
  ],
}

function simularApi() {
  let listas = 0
  const mock = vi.fn<typeof fetch>((entrada, opciones) => {
    const ruta = new URL(String(entrada), 'http://localhost').pathname
    if (ruta.endsWith('/contenido')) return Promise.resolve(new Response(new Blob(['png'])))
    if (opciones?.method === 'POST')
      return Promise.resolve(respuesta(200, { ...DETALLE, estado: 'devuelto' }))
    if (ruta.endsWith('/pagos/p1')) return Promise.resolve(respuesta(200, DETALLE))
    // Decidido el pago, ya no figura por verificar.
    listas += 1
    return Promise.resolve(respuesta(200, listas > 1 ? [] : [PAGO]))
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

describe('PorVerificarView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    URL.createObjectURL = vi.fn<typeof URL.createObjectURL>(() => 'blob:voucher')
    URL.revokeObjectURL = vi.fn<typeof URL.revokeObjectURL>()
    // jsdom no implementa close en <dialog>: se cierra quitando el atributo, como el navegador.
    HTMLDialogElement.prototype.close = vi.fn<HTMLDialogElement['close']>(function (
      this: HTMLDialogElement,
    ) {
      this.removeAttribute('open')
    })
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('muestra la confianza, lo comprobado y lo leído del voucher', async () => {
    simularApi()
    const vista = await montar()

    expect(vista.text()).toContain('64 %')
    expect(vista.text()).toContain('Confianza media')
    expect(vista.text()).toContain('La empresa pagada no parece la del documento.')
    expect(vista.text()).toContain('MOVISTAR')
    expect(vista.get('img').attributes('src')).toBe('blob:voucher')
  })

  it('devolver pide un motivo y lo envía al backend', async () => {
    const api = simularApi()
    const vista = await montar()

    await vista
      .findAll('button')
      .find((b) => b.text() === 'Devolver')!
      .trigger('click')
    await vista.get('textarea').setValue('El voucher es de otro mes.')
    await vista.get('form').trigger('submit')
    await flushPromises()

    const envio = api.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(String(envio?.[0])).toContain('/pagos/p1/devolucion')
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({ motivo: 'El voucher es de otro mes.' })
    expect(vista.text()).toContain('Devolviste el pago de «Luz de la casa»')
  })
})
