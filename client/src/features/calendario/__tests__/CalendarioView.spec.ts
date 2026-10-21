import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta } from '@/features/acceso/__tests__/respuestas'

import CalendarioView from '../views/CalendarioView.vue'

const VENCIMIENTO = {
  deuda_id: 'd1',
  concepto: 'Luz de la casa',
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  lugar_pago: 'agente',
  estado: 'registrada',
  revision_pendiente: false,
  vence_el: '2026-10-22',
  importe: '182.40',
  cuota: 1,
  cuotas: 1,
  registrada_por: 'Lucía Vega',
}

const calendario = (vencimientos: unknown[] = [VENCIMIENTO]) => ({
  hoy: '2026-10-21',
  desde: '2026-09-28',
  hasta: '2026-11-08',
  vencimientos,
})

/** Responde según la ruta: el calendario con lo dado y las categorías vacías. */
function simularApi(porRango: (url: URL) => Response) {
  const mock = vi.fn<typeof fetch>((entrada) => {
    const url = new URL(String(entrada), 'http://localhost')
    if (url.pathname.endsWith('/categorias')) return Promise.resolve(respuesta(200, []))
    return Promise.resolve(porRango(url))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

async function montar(query = '?mes=2026-10&dia=2026-10-21') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/calendario', name: 'calendario', component: CalendarioView },
      { path: '/ingresar', name: 'inicio-sesion', component: { template: '<p />' } },
      { path: '/registrar-deuda', name: 'registrar-deuda', component: { template: '<p />' } },
      { path: '/por-autorizar', name: 'por-autorizar', component: { template: '<p />' } },
    ],
  })
  await router.push(`/calendario${query}`)
  const vista = mount(
    { template: '<RouterView />' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { vista, router }
}

const dia = (vista: Awaited<ReturnType<typeof montar>>['vista'], fecha: string) =>
  vista.get(`[data-dia="${fecha}"]`)

describe('CalendarioView', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('pide las seis semanas del mes y marca el día que vence cada deuda', async () => {
    const api = simularApi(() => respuesta(200, calendario()))
    const { vista } = await montar()

    const rangos = api.mock.calls
      .map(([entrada]) => new URL(String(entrada), 'http://localhost'))
      .filter((url) => url.pathname.endsWith('/deudas/calendario'))
      .map((url) => `${url.searchParams.get('desde')}→${url.searchParams.get('hasta')}`)
    expect(rangos).toContain('2026-09-28→2026-11-08')
    expect(dia(vista, '2026-10-22').attributes('aria-label')).toContain('1 vencimiento')
    expect(dia(vista, '2026-10-21').attributes('aria-current')).toBe('date')
    // Lo que vence mañana se ve sin buscarlo.
    expect(vista.text()).toContain('Vence mañana')
  })

  it('al elegir un día muestra lo que vence y el día queda en la dirección', async () => {
    simularApi(() => respuesta(200, calendario()))
    const { vista, router } = await montar()

    expect(vista.get('aside').text()).toContain('Un día despejado.')
    await dia(vista, '2026-10-22').trigger('click')
    await flushPromises()

    const panel = vista.get('aside').text()
    expect(panel).toContain('Luz de la casa')
    expect(panel).toContain('182.40')
    expect(router.currentRoute.value.query.dia).toBe('2026-10-22')
  })

  it('las flechas recorren los días y al salir del mes cargan el siguiente', async () => {
    const api = simularApi(() => respuesta(200, calendario([])))
    const { vista, router } = await montar('?mes=2026-10&dia=2026-10-31')

    await dia(vista, '2026-10-31').trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()

    expect(router.currentRoute.value.query).toMatchObject({ mes: '2026-11', dia: '2026-11-01' })
    const pedidos = api.mock.calls.map(([entrada]) => String(entrada))
    expect(pedidos.some((url) => url.includes('desde=2026-10-26&hasta=2026-12-06'))).toBe(true)
  })

  it('si la API falla lo dice y deja volver a intentar', async () => {
    let falla = true
    simularApi(() =>
      falla
        ? respuesta(503, { code: 'SERVICIO_NO_DISPONIBLE', detail: 'Intenta en unos minutos.' })
        : respuesta(200, calendario()),
    )
    const { vista } = await montar()

    expect(vista.get('[role="alert"]').text()).toContain('Intenta en unos minutos.')
    falla = false
    await vista.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(vista.find('[role="alert"]').exists()).toBe(false)
    expect(dia(vista, '2026-10-22').attributes('aria-label')).toContain('1 vencimiento')
  })
})
