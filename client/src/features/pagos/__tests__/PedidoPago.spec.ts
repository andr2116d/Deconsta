import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { respuesta, SESION_HABILITADA } from '@/features/acceso/__tests__/respuestas'
import { useSesionStore } from '@/features/acceso/stores/sesion'

import AvisoPedidoPago from '../components/AvisoPedidoPago.vue'
import PagosPorCompletarView from '../views/PagosPorCompletarView.vue'

const PEDIDO = {
  id: 'p1',
  deuda_id: 'd1',
  concepto: 'Luz de la oficina',
  cuota: 1,
  cuotas: 1,
  importe: '182.40',
  vence_el: '2026-10-10',
  vencida_hace: 11,
  asistente_id: 'a1',
  asistente: 'Lucía Vega',
  nota: 'Hoy sin falta, antes del corte.',
  pedido_en: '2026-10-21T15:00:00Z',
}

const cuota = (pedido: unknown = null) => ({
  deuda_id: 'd1',
  concepto: 'Luz de la oficina',
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  lugares_pago: ['agente'],
  codigo_pago: null,
  cuota: 1,
  cuotas: 1,
  vence_el: '2026-10-10',
  importe: '182.40',
  vencida_hace: 11,
  registrada_por: 'Valentina Ramos',
  devuelto_por: null,
  mora: null,
  pedido,
})

const ASISTENTE = {
  id: 'a1',
  nombre_usuario: 'lucia.vega',
  nombres: 'Lucía',
  apellidos: 'Vega',
  estado: 'activa',
  bloqueada: false,
}

/** Responde según la ruta y guarda cada envío para revisarlo. */
function simularApi(rutas: Record<string, unknown>) {
  const envios: Array<{ ruta: string; cuerpo: unknown }> = []
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>((entrada, opciones) => {
      const ruta = new URL(String(entrada), 'http://localhost').pathname.replace('/api/v1', '')
      if (opciones?.method === 'POST') {
        envios.push({ ruta, cuerpo: opciones.body ? JSON.parse(String(opciones.body)) : null })
        return Promise.resolve(respuesta(ruta.endsWith('/retiro') ? 204 : 201, PEDIDO))
      }
      return Promise.resolve(respuesta(200, ruta in rutas ? rutas[ruta] : []))
    }),
  )
  return envios
}

function iniciarSesion(rol: 'gerente' | 'asistente') {
  const sesion = useSesionStore()
  sesion.sesion = structuredClone({
    ...SESION_HABILITADA,
    usuario: { ...SESION_HABILITADA.usuario, rol },
  }) as typeof sesion.sesion
}

async function montar(componente: object) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'pagos-por-completar', component: componente },
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
  return { vista, router }
}

describe('Pedido de pago', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('a la asistente le sale el aviso a pantalla completa con la nota y el importe', async () => {
    iniciarSesion('asistente')
    simularApi({ '/pagos/pedidos': [PEDIDO] })

    const { vista } = await montar(AvisoPedidoPago)

    const dialogo = vista.get('dialog')
    expect(dialogo.attributes('open')).toBeDefined()
    expect(dialogo.text()).toContain('Este pago necesita tu atención, Lucía.')
    expect(dialogo.text()).toContain('Hoy sin falta, antes del corte.')
    expect(dialogo.text()).toContain('182.40')
    expect(vista.find('[role="region"]').exists()).toBe(false)
  })

  it('«Ver después» cierra el aviso y deja la barra arriba', async () => {
    iniciarSesion('asistente')
    simularApi({ '/pagos/pedidos': [PEDIDO] })
    const { vista } = await montar(AvisoPedidoPago)

    const despues = vista.findAll('dialog button').find((b) => b.text() === 'Ver después')!
    await despues.trigger('click')
    await flushPromises()

    expect(vista.get('dialog').attributes('open')).toBeUndefined()
    const barra = vista.get('[role="region"]')
    expect(barra.text()).toContain('Tu gerente te pidió pagar «Luz de la oficina».')
    expect(barra.get('a').attributes('href')).toBe('/pagos/registrar?deuda=d1&cuota=1')
    expect(JSON.parse(sessionStorage.getItem('deconsta:pedidos-pospuestos')!).ids).toEqual(['p1'])
  })

  it('sin pedidos no interrumpe a la asistente', async () => {
    iniciarSesion('asistente')
    simularApi({ '/pagos/pedidos': [] })
    const { vista } = await montar(AvisoPedidoPago)

    expect(vista.get('dialog').attributes('open')).toBeUndefined()
    expect(vista.find('[role="region"]').exists()).toBe(false)
  })

  it('el gerente pide el pago a su única asistente, que ya viene elegida', async () => {
    iniciarSesion('gerente')
    const envios = simularApi({
      '/pagos/por-pagar': { hoy: '2026-10-21', registro_bloqueado: false, cuotas: [cuota()] },
      '/asistentes': [ASISTENTE],
    })
    const { vista } = await montar(PagosPorCompletarView)

    await vista.get('button[aria-label="Pedir que paguen Luz de la oficina"]').trigger('click')
    await flushPromises()
    expect((vista.get('select').element as HTMLSelectElement).value).toBe('a1')
    await vista.get('textarea').setValue('  Hoy sin falta.  ')
    await vista.get('dialog form').trigger('submit')
    await flushPromises()

    expect(envios).toEqual([
      {
        ruta: '/pagos/pedidos',
        cuerpo: { deuda_id: 'd1', cuota: 1, asistente_id: 'a1', nota: 'Hoy sin falta.' },
      },
    ])
  })

  it('la cuota pedida dice a quién y el gerente puede retirar el pedido', async () => {
    iniciarSesion('gerente')
    const envios = simularApi({
      '/pagos/por-pagar': {
        hoy: '2026-10-21',
        registro_bloqueado: false,
        cuotas: [cuota({ id: 'p1', asistente_id: 'a1', asistente: 'Lucía Vega', nota: null })],
      },
    })
    const { vista } = await montar(PagosPorCompletarView)

    expect(vista.text()).toContain('Pedido a Lucía Vega')
    await vista
      .get('button[aria-label="Retirar el pedido de pagar Luz de la oficina"]')
      .trigger('click')
    await flushPromises()

    expect(envios.map((e) => e.ruta)).toEqual(['/pagos/pedidos/p1/retiro'])
  })
})
