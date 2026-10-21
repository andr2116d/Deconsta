import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta, SESION_HABILITADA } from '@/features/acceso/__tests__/respuestas'
import { useSesionStore } from '@/features/acceso/stores/sesion'

import PanelView from '../views/PanelView.vue'

const CUOTA = {
  deuda_id: 'd2',
  concepto: 'Agua de la casa',
  categoria_id: null,
  cuota: 1,
  cuotas: 1,
  importe: '95.50',
  vence_el: '2026-10-25',
  lugares_pago: ['agente'],
  pedido: null,
}

const RESUMEN = {
  hoy: '2026-10-21',
  rol: 'gerente',
  jornada: null,
  resumen: {
    por_pagar: '277.90',
    cuotas_por_pagar: 2,
    vencidas: 1,
    pagado_mes: '182.40',
    pagos_mes: 1,
    pendientes: [
      {
        tipo: 'verificar_pago',
        id: 'p1',
        deuda_id: 'd1',
        concepto: 'Luz de la casa',
        importe: '182.40',
        vence_el: '2026-10-10',
        por: 'Lucía Vega',
        desde: '2026-10-21T10:00:00Z',
      },
      {
        tipo: 'autorizar_deuda',
        id: 'd3',
        deuda_id: 'd3',
        concepto: 'Internet de la casa',
        importe: '320.00',
        vence_el: '2026-10-30',
        por: 'Lucía Vega',
        desde: '2026-10-21T11:00:00Z',
      },
    ],
    proximas: [
      { ...CUOTA, pedido: { id: 'x', asistente_id: 'a1', asistente: 'Lucía Vega', nota: null } },
    ],
  },
}

const JORNADA = {
  hoy: '2026-10-21',
  rol: 'asistente',
  resumen: null,
  jornada: {
    por_completar: 2,
    devueltas: 1,
    en_manos_del_gerente: 3,
    gerente: 'Valentina Ramos',
    siguiente: {
      ...CUOTA,
      pedido: { id: 'x', asistente_id: 'a1', asistente: 'Lucía Vega', nota: 'Antes del corte.' },
    },
    limite: '100.00',
  },
}

function iniciarSesion(rol: 'gerente' | 'asistente') {
  const sesion = useSesionStore()
  sesion.sesion = structuredClone({
    ...SESION_HABILITADA,
    usuario: { ...SESION_HABILITADA.usuario, rol },
  }) as typeof sesion.sesion
}

function simularApi(panel: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((entrada) =>
      Promise.resolve(respuesta(200, String(entrada).endsWith('/panel') ? panel : [])),
    ),
  )
}

async function montar() {
  const vacia = { template: '<p />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'inicio', component: PanelView },
      ...[
        'pagos-por-completar',
        'por-autorizar',
        'por-verificar',
        'mis-registros',
        'historial',
        'registrar-deuda',
        'registrar-pago',
        'inicio-sesion',
      ].map((name) => ({ path: `/${name}`, name, component: vacia })),
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

describe('PanelView', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('al gerente le muestra sus cifras y lleva a cada decisión', async () => {
    iniciarSesion('gerente')
    simularApi(RESUMEN)

    const vista = await montar()

    expect(vista.text()).toContain('Lo que necesita tu decisión.')
    expect(vista.text()).toContain('2 cuotas · 1 vencidas')
    const bandeja = vista.get('ul').findAll('a')
    expect(bandeja.map((a) => a.attributes('href'))).toEqual([
      '/por-verificar?pago=p1',
      '/por-autorizar?deuda=d3',
    ])
    expect(vista.text()).toContain('Pedido a Lucía Vega')
  })

  it('a la asistente le pone primero lo que le pidió su gerente', async () => {
    iniciarSesion('asistente')
    simularApi(JORNADA)

    const vista = await montar()

    expect(vista.text()).toContain('Lucía, esto sigue en tu jornada.')
    expect(vista.text()).toContain('Valentina te pidió pagarla')
    expect(vista.text()).toContain('«Antes del corte.»')
    expect(vista.text()).toContain('En manos de Valentina')
    const pagar = vista.findAll('a').find((a) => a.text().includes('subir comprobante'))!
    expect(pagar.attributes('href')).toBe('/registrar-pago?deuda=d2&cuota=1')
  })
})
