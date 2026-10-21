import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta } from '@/features/acceso/__tests__/respuestas'

import PagosPorCompletarView from '../views/PagosPorCompletarView.vue'

const cuota = (concepto: string, vence_el: string, vencida_hace: number | null) => ({
  deuda_id: concepto,
  concepto,
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  lugares_pago: ['agente', 'billetera'],
  codigo_pago: null,
  cuota: 1,
  cuotas: 1,
  vence_el,
  importe: '100.00',
  vencida_hace,
  registrada_por: 'Valentina Ramos',
})

function simularApi(porPagar: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((entrada) => {
      const ruta = new URL(String(entrada), 'http://localhost').pathname
      if (ruta.endsWith('/pagos/por-pagar')) return Promise.resolve(respuesta(200, porPagar))
      return Promise.resolve(respuesta(200, []))
    }),
  )
}

async function montar() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'pagos-por-completar', component: PagosPorCompletarView },
      { path: '/pagos/registrar', name: 'registrar-pago', component: { template: '<p />' } },
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

describe('PagosPorCompletarView', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('ordena lo que falta pagar por urgencia y lleva a registrar cada pago', async () => {
    simularApi({
      hoy: '2026-10-21',
      registro_bloqueado: false,
      cuotas: [
        cuota('Luz', '2026-10-10', 11),
        cuota('Agua', '2026-10-23', null),
        cuota('Internet', '2026-11-15', null),
      ],
    })
    const vista = await montar()

    const grupos = vista.findAll('section section h2').map((h) => h.text())
    expect(grupos).toEqual([
      expect.stringContaining('Vencidas · 1'),
      expect.stringContaining('Vencen esta semana · 1'),
      expect.stringContaining('Más adelante · 1'),
    ])
    expect(vista.text()).toContain('Venció hace 11 días')
    expect(vista.text()).toContain('Agente o agencia, Billetera digital')
    const enlace = vista.get('a[aria-label="Registrar el pago de Luz"]')
    expect(enlace.attributes('href')).toBe('/pagos/registrar?deuda=Luz&cuota=1')
  })

  it('con el registro en pausa lo explica y no ofrece registrar pagos', async () => {
    simularApi({
      hoy: '2026-10-21',
      registro_bloqueado: true,
      cuotas: [cuota('Luz', '2026-10-23', null)],
    })
    const vista = await montar()

    expect(vista.text()).toContain('Tu registro de pagos está en pausa')
    expect(vista.find('a[aria-label="Registrar el pago de Luz"]').exists()).toBe(false)
  })
})
