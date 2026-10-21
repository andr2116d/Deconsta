import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta, SESION_HABILITADA } from '@/features/acceso/__tests__/respuestas'
import { useSesionStore } from '@/features/acceso/stores/sesion'

import HistorialView from '../views/HistorialView.vue'

const deuda = (id: string, concepto: string, cambios: Record<string, unknown> = {}) => ({
  id,
  concepto,
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  lugares_pago: ['agente'],
  importe: '182.40',
  estado: 'registrada',
  revision_pendiente: false,
  motivos: [],
  registrada_por: 'Lucía Vega',
  registrada_por_id: 'a1',
  creado_en: '2026-10-20T15:00:00Z',
  motivo_decision: null,
  cuotas: [
    { numero: 1, vence_el: '2026-10-10', importe: '182.40', pago: 'por_verificar', mora: null },
  ],
  pagos: [
    {
      id: 'p1',
      cuota: 1,
      importe: '182.40',
      comision: '0.00',
      mora: '0.00',
      lugar_pago: 'agente',
      pagado_el: '2026-10-20',
      estado: 'por_verificar',
      confianza: 81,
      registrado_por: 'Lucía Vega',
      registrado_en: '2026-10-20T16:00:00Z',
      decidido_en: null,
      motivo_decision: null,
    },
  ],
  moras: [],
  eventos: [
    {
      accion: 'DEUDA_REGISTRADA',
      en: '2026-10-20T15:00:00Z',
      actor: 'Lucía Vega',
      motivo: null,
      cuota: null,
    },
    {
      accion: 'PAGO_REGISTRADO',
      en: '2026-10-20T16:00:00Z',
      actor: 'Lucía Vega',
      motivo: null,
      cuota: 1,
    },
  ],
  ...cambios,
})

const pagina = (deudas: unknown[], siguiente: string | null = null) => ({
  hoy: '2026-10-21',
  desde: '2026-07-24',
  hasta: '2026-10-21',
  deudas,
  siguiente,
})

/** Responde el historial según el cursor y guarda cada consulta. */
function simularApi(paginas: Record<string, unknown>) {
  const consultas: URLSearchParams[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((entrada) => {
      const url = new URL(String(entrada), 'http://localhost')
      if (url.pathname.endsWith('/historial')) {
        consultas.push(url.searchParams)
        return Promise.resolve(respuesta(200, paginas[url.searchParams.get('cursor') ?? '']))
      }
      return Promise.resolve(respuesta(200, []))
    }),
  )
  return consultas
}

function iniciarSesion(rol: 'gerente' | 'asistente') {
  const sesion = useSesionStore()
  sesion.sesion = structuredClone({
    ...SESION_HABILITADA,
    usuario: { ...SESION_HABILITADA.usuario, rol },
  }) as typeof sesion.sesion
}

async function montar(ruta: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/historial', name: 'historial', component: HistorialView },
      { path: '/mis-registros', name: 'mis-registros', component: HistorialView },
      { path: '/ingresar', name: 'inicio-sesion', component: { template: '<p />' } },
    ],
  })
  await router.push(ruta)
  const vista = mount(
    { template: '<RouterView />' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { vista, router }
}

describe('HistorialView', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('al gerente le resalta lo pendiente y le cuenta quién hizo qué', async () => {
    iniciarSesion('gerente')
    simularApi({ '': pagina([deuda('d1', 'Luz de la casa')]) })

    const { vista } = await montar('/historial')

    const tarjeta = vista.get('article')
    expect(tarjeta.classes()).toContain('border-aviso/60')
    expect(tarjeta.text()).toContain('Pago por verificar')
    expect(tarjeta.text()).toContain('81 %')
    expect(tarjeta.get('details').text()).toContain('Lucía Vega registró el pago')
    expect(vista.text()).toContain('Exportar CSV')
  })

  it('los filtros salen de la dirección y vuelven a ella al cambiar', async () => {
    iniciarSesion('gerente')
    const consultas = simularApi({ '': pagina([deuda('d1', 'Luz de la casa')]) })

    const { vista, router } = await montar('/historial?estado=por_verificar&q=luz')

    expect(consultas[0]!.get('estado')).toBe('por_verificar')
    expect(consultas[0]!.get('q')).toBe('luz')
    expect((vista.get('input[type="search"]').element as HTMLInputElement).value).toBe('luz')
    await vista.findAll('select')[0]!.setValue('rechazada')
    await flushPromises()

    expect(consultas[consultas.length - 1]!.get('estado')).toBe('rechazada')
    expect(router.currentRoute.value.query).toEqual({ estado: 'rechazada', q: 'luz' })
  })

  it('«Mis registros» pide solo lo de la asistente, sin exportar ni confianza', async () => {
    iniciarSesion('asistente')
    const consultas = simularApi({
      '': pagina([deuda('d1', 'Luz de la casa', { pagos: [] })], 'c2'),
      c2: pagina([deuda('d2', 'Agua de la casa', { pagos: [] })]),
    })

    const { vista } = await montar('/mis-registros')

    expect(consultas[0]!.get('mios')).toBe('true')
    expect(vista.text()).not.toContain('Exportar CSV')
    expect(vista.get('article').classes()).not.toContain('border-aviso/60')
    await vista
      .findAll('button')
      .find((b) => b.text() === 'Ver más')!
      .trigger('click')
    await flushPromises()

    expect(consultas[consultas.length - 1]!.get('cursor')).toBe('c2')
    expect(vista.findAll('article').map((a) => a.get('h3').text())).toEqual([
      'Luz de la casa',
      'Agua de la casa',
    ])
  })

  it('sin movimientos lo dice', async () => {
    iniciarSesion('gerente')
    simularApi({ '': pagina([]) })

    const { vista } = await montar('/historial')

    expect(vista.text()).toContain('Todavía no hay movimientos.')
  })
})
