import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta } from '@/features/acceso/__tests__/respuestas'

import RegistrarPagoView from '../views/RegistrarPagoView.vue'

const CUOTA = {
  deuda_id: 'd1',
  concepto: 'Luz de la casa',
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  lugares_pago: ['agente'],
  codigo_pago: '54871236',
  cuota: 1,
  cuotas: 1,
  vence_el: '2026-10-10',
  importe: '182.40',
  vencida_hace: 11,
  registrada_por: 'Lucía Vega',
  devuelto_por: null,
  mora: null,
}
const comprobante = (id: string, cambios: Record<string, unknown>) => ({
  id,
  deuda_id: 'd1',
  cuota: 1,
  estado: 'analizando',
  tipo_archivo: 'image/png',
  nombre_archivo: 'voucher.png',
  tamano: 1000,
  subido_en: '2026-10-21T10:00:00Z',
  analizado_en: null,
  riesgo: null,
  senales: [],
  lectura: null,
  pago_id: null,
  proposito: 'pago',
  registro_bloqueado: false,
  ...cambios,
})
const lectura = (importe: string) => ({
  lugar: 'agente',
  medio: 'Agente BCP',
  empresa: 'HIDRANDINA',
  numero_operacion: '0458213',
  pagado_el: '2026-10-21',
  importe,
  comision: null,
  mora: null,
})

/** Un voucher con mora (c1) y, al subirlo como prueba, la prueba lista (c2). */
function simularApi(cuota: Record<string, unknown> = CUOTA, voucher?: Record<string, unknown>) {
  let subidas = 0
  const mock = vi.fn<typeof fetch>((entrada, opciones) => {
    const ruta = new URL(String(entrada), 'http://localhost').pathname
    if (ruta.endsWith('/pagos/por-pagar'))
      return Promise.resolve(
        respuesta(200, { hoy: '2026-10-21', cuotas: [cuota], registro_bloqueado: false }),
      )
    if (ruta.endsWith('/pagos/comprobantes')) {
      subidas += 1
      return Promise.resolve(respuesta(202, comprobante(`c${subidas}`, {})))
    }
    if (ruta.endsWith('/comprobantes/c1') && voucher)
      return Promise.resolve(respuesta(200, comprobante('c1', voucher)))
    if (ruta.endsWith('/pagos') && opciones?.method === 'POST')
      return Promise.resolve(respuesta(201, { id: 'p1', estado: 'por_verificar' }))
    if (ruta.endsWith('/comprobantes/c1'))
      return Promise.resolve(
        respuesta(
          200,
          comprobante('c1', {
            estado: 'rechazado',
            lectura: lectura('196.80'),
            senales: [
              {
                capa: 'ia',
                codigo: 'POSIBLE_MORA',
                detalle: 'El voucher paga S/ 196.80, S/ 14.40 más que la cuota.',
                riesgo: 'alto',
              },
            ],
          }),
        ),
      )
    if (ruta.endsWith('/comprobantes/c2'))
      return Promise.resolve(
        respuesta(
          200,
          comprobante('c2', { estado: 'listo', proposito: 'mora', lectura: lectura('196.80') }),
        ),
      )
    if (ruta.endsWith('/pagos/moras') && opciones?.method === 'POST')
      return Promise.resolve(respuesta(201, { id: 'm1', estado: 'por_aprobar' }))
    return Promise.resolve(respuesta(404, { code: 'NO_ENCONTRADO', detail: 'No.' }))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

async function montar() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/pagos/registrar', name: 'registrar-pago', component: RegistrarPagoView },
      { path: '/pagos', name: 'pagos-por-completar', component: { template: '<p />' } },
      { path: '/calendario', name: 'calendario', component: { template: '<p />' } },
      { path: '/ingresar', name: 'inicio-sesion', component: { template: '<p />' } },
    ],
  })
  await router.push('/pagos/registrar?deuda=d1&cuota=1')
  const vista = mount(
    { template: '<RouterView />' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return vista
}

const boton = (vista: Awaited<ReturnType<typeof montar>>, texto: string) =>
  vista.findAll('button').find((b) => b.text().includes(texto))

describe('La mora al registrar un pago', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    URL.createObjectURL = vi.fn<typeof URL.createObjectURL>(() => 'blob:vista')
    URL.revokeObjectURL = vi.fn<typeof URL.revokeObjectURL>()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('el voucher que pagó con mora sirve de prueba con la mora calculada', async () => {
    const api = simularApi()
    const vista = await montar()
    expect(vista.text()).toContain('¿la empresa te cobra mora?')

    const archivo = new File([new Uint8Array([137, 80, 78, 71])], 'voucher.png', {
      type: 'image/png',
    })
    const entrada = vista.get('input[type="file"][multiple]')
    Object.defineProperty(entrada.element, 'files', { value: [archivo] })
    await entrada.trigger('change')
    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()
    await boton(vista, 'Declarar la mora con este voucher')!.trigger('click')
    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()

    const campo = vista.get('input[inputmode="decimal"]').element as HTMLInputElement
    expect(campo.value).toBe('14.40')
    const prueba = api.mock.calls.find(
      ([e, o]) =>
        String(e).endsWith('/pagos/comprobantes') &&
        o?.body instanceof FormData &&
        (o.body as FormData).get('proposito') === 'mora',
    )
    expect(prueba).toBeDefined()
    await vista.get('form').trigger('submit')
    await flushPromises()

    const declaracion = api.mock.calls.find(([e]) => String(e).endsWith('/pagos/moras'))
    expect(JSON.parse(String(declaracion?.[1]?.body))).toMatchObject({
      deuda_id: 'd1',
      cuota: 1,
      importe: '14.40',
      prueba_id: 'c2',
    })
  })

  it('mientras la mora espera al gerente no se suben vouchers', async () => {
    simularApi({
      ...CUOTA,
      mora: { id: 'm1', estado: 'por_aprobar', importe: '14.40', motivo_decision: null },
    })
    const vista = await montar()

    expect(vista.text()).toContain('La mora espera a tu gerente')
    expect(boton(vista, 'Elegir voucher')!.attributes('disabled')).toBeDefined()
  })

  it('con la mora aprobada acepta la cuota más la mora y registra el pago', async () => {
    const api = simularApi(
      { ...CUOTA, mora: { id: 'm1', estado: 'aprobada', importe: '14.40', motivo_decision: null } },
      { estado: 'listo', lectura: lectura('196.80') },
    )
    const vista = await montar()
    expect(vista.text()).toContain('Mora aprobada')

    const archivo = new File([new Uint8Array([137, 80, 78, 71])], 'voucher.png', {
      type: 'image/png',
    })
    const entrada = vista.get('input[type="file"][multiple]')
    Object.defineProperty(entrada.element, 'files', { value: [archivo] })
    await entrada.trigger('change')
    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()

    const registrar = boton(vista, 'Registrar pago')!
    expect(registrar.attributes('disabled')).toBeUndefined()
    await registrar.trigger('click')
    await flushPromises()
    const registro = api.mock.calls.find(
      ([e, o]) => String(e).endsWith('/pagos') && o?.method === 'POST',
    )
    expect(JSON.parse(String(registro?.[1]?.body))).toEqual({
      deuda_id: 'd1',
      cuota: 1,
      comprobantes: ['c1'],
    })
  })
})
