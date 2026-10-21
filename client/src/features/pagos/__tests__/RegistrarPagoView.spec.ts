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
  vence_el: '2026-10-28',
  importe: '182.40',
  vencida_hace: null,
  registrada_por: 'Lucía Vega',
}
const POR_PAGAR = { hoy: '2026-10-21', cuotas: [CUOTA], registro_bloqueado: false }
const SUBIDO = {
  id: 'c1',
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
  registro_bloqueado: false,
}
const lectura = (importe: string) => ({
  lugar: 'agente',
  medio: 'Agente BCP',
  empresa: 'HIDRANDINA',
  numero_operacion: '0458213',
  pagado_el: '2026-10-21',
  importe,
  comision: null,
})
const PAGO = {
  id: 'p1',
  deuda_id: 'd1',
  concepto: 'Luz de la casa',
  cuota: 1,
  importe: '182.40',
  comision: '0.00',
  lugar_pago: 'agente',
  pagado_el: '2026-10-21',
  estado: 'por_verificar',
  confianza: 88,
  comprobaciones: [],
  comprobantes: ['c1'],
  registrado_por: 'Lucía Vega',
  registrado_en: '2026-10-21T10:01:00Z',
}

/** El servidor según la ruta: la cuota por pagar, la subida, su análisis y el registro. */
function simularApi(analizado: Record<string, unknown>) {
  const mock = vi.fn<typeof fetch>((entrada, opciones) => {
    const ruta = new URL(String(entrada), 'http://localhost').pathname
    if (ruta.endsWith('/pagos/por-pagar')) return Promise.resolve(respuesta(200, POR_PAGAR))
    if (ruta.endsWith('/pagos/comprobantes')) return Promise.resolve(respuesta(202, SUBIDO))
    if (ruta.includes('/pagos/comprobantes/')) return Promise.resolve(respuesta(200, analizado))
    if (ruta.endsWith('/pagos') && opciones?.method === 'POST')
      return Promise.resolve(respuesta(201, PAGO))
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

async function subir(vista: Awaited<ReturnType<typeof montar>>) {
  const archivo = new File([new Uint8Array([137, 80, 78, 71])], 'voucher.png', {
    type: 'image/png',
  })
  const entrada = vista.get('input[type="file"]')
  Object.defineProperty(entrada.element, 'files', { value: [archivo], configurable: true })
  await entrada.trigger('change')
  await flushPromises()
  await vi.advanceTimersByTimeAsync(1300)
  await flushPromises()
}

const boton = (vista: Awaited<ReturnType<typeof montar>>) =>
  vista.findAll('button').find((b) => b.text().includes('Registrar pago'))!

describe('RegistrarPagoView', () => {
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

  it('con un voucher que cubre la cuota registra el pago y lo envía al gerente', async () => {
    const api = simularApi({ ...SUBIDO, estado: 'listo', lectura: lectura('182.40') })
    const vista = await montar()
    expect(boton(vista).attributes('disabled')).toBeDefined()

    await subir(vista)

    expect(vista.text()).toContain('Listo')
    expect(boton(vista).attributes('disabled')).toBeUndefined()
    await boton(vista).trigger('click')
    await flushPromises()

    const registro = api.mock.calls.find(
      ([, o]) => o?.method === 'POST' && !(o.body instanceof FormData),
    )
    expect(JSON.parse(String(registro?.[1]?.body))).toEqual({
      deuda_id: 'd1',
      cuota: 1,
      comprobantes: ['c1'],
    })
    expect(vista.text()).toContain('Pago enviado a tu gerente.')
    // A la asistente no se le muestra la confianza: es para el gerente.
    expect(vista.text()).not.toContain('88')
  })

  it('un voucher de agente por menos pide los demás vouchers y no deja registrar', async () => {
    simularApi({
      ...SUBIDO,
      estado: 'listo',
      lectura: lectura('100.00'),
      senales: [
        {
          capa: 'ia',
          codigo: 'PAGO_PARCIAL',
          detalle: 'Este voucher paga una parte.',
          riesgo: 'bajo',
        },
      ],
    })
    const vista = await montar()

    await subir(vista)

    expect(vista.text()).toContain('¿El agente te lo cobró por partes?')
    expect(vista.text()).toMatch(/Falta\s+S\/\s82\.40/)
    expect(boton(vista).attributes('disabled')).toBeDefined()
  })

  it('un voucher que no corresponde dice por qué y no suma', async () => {
    simularApi({
      ...SUBIDO,
      estado: 'rechazado',
      riesgo: 'alto',
      lectura: lectura('182.40'),
      senales: [
        {
          capa: 'ia',
          codigo: 'CODIGO_DISTINTO',
          detalle: 'El voucher paga otro código de pago o suministro, no el de esta deuda.',
          riesgo: 'alto',
        },
      ],
    })
    const vista = await montar()

    await subir(vista)

    expect(vista.text()).toContain('No corresponde')
    expect(vista.text()).toContain('paga otro código de pago')
    expect(vista.text()).toContain('0 vouchers listos')
    expect(boton(vista).attributes('disabled')).toBeDefined()
  })
})
