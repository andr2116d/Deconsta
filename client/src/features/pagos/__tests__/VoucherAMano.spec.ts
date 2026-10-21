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

/** El voucher falla al leerse; al escribir sus datos, el backend lo devuelve listo. */
function simularApi() {
  const mock = vi.fn<typeof fetch>((entrada, opciones) => {
    const ruta = new URL(String(entrada), 'http://localhost').pathname
    if (ruta.endsWith('/pagos/por-pagar')) return Promise.resolve(respuesta(200, POR_PAGAR))
    if (ruta.endsWith('/pagos/comprobantes')) return Promise.resolve(respuesta(202, SUBIDO))
    if (ruta.endsWith('/comprobantes/c1/datos'))
      return Promise.resolve(
        respuesta(200, {
          ...SUBIDO,
          estado: 'listo',
          lectura: { ...lectura('182.40'), numero_operacion: '0458777' },
          senales: [
            { capa: 'lectura', codigo: 'DATOS_A_MANO', detalle: 'A mano.', riesgo: 'medio' },
          ],
        }),
      )
    if (ruta.endsWith('/comprobantes/c1'))
      return Promise.resolve(respuesta(200, { ...SUBIDO, estado: 'fallido', proposito: 'pago' }))
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

describe('Voucher que no se pudo leer', () => {
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

  it('se escriben sus datos y el pago se puede registrar', async () => {
    const api = simularApi()
    const vista = await montar()
    await subir(vista)
    expect(vista.text()).toContain('No pudimos leerlo solo.')
    expect(boton(vista).attributes('disabled')).toBeDefined()

    await vista
      .findAll('button')
      .find((b) => b.text() === 'Escribir los datos')!
      .trigger('click')
    const formulario = vista.get('form[aria-label="Escribe los datos del voucher"]')
    expect((formulario.get('input[inputmode="decimal"]').element as HTMLInputElement).value).toBe(
      '182.40',
    )
    await formulario.get('input[autocomplete="off"]').setValue('0458777')
    await formulario.get('select').setValue('agente')
    await formulario.trigger('submit')
    await flushPromises()

    const envio = api.mock.calls.find(([e]) => String(e).endsWith('/comprobantes/c1/datos'))
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({
      importe: '182.40',
      pagado_el: '2026-10-21',
      numero_operacion: '0458777',
      lugar: 'agente',
      comision: '',
    })
    expect(vista.text()).toContain('Datos escritos a mano')
    expect(boton(vista).attributes('disabled')).toBeUndefined()
  })
})
