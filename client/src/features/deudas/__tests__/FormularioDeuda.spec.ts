import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'

import FormularioDeuda from '../components/FormularioDeuda.vue'
import type { Documento, Propuesta } from '../types'

const PROPUESTA: Propuesta = {
  tipo: 'recibo_servicio',
  concepto: 'Luz Hidrandina setiembre 2026',
  emisor: 'Hidrandina S.A.',
  titular_nombre: 'RAMOS DIAZ VALENTINA',
  titular_tipo_documento: null,
  titular_numero_documento: null,
  codigo_pago: '54871236',
  numero_documento: 'S001-00451236',
  periodo: '2026-09',
  importe: '182.40',
  vence_el: '2026-10-28',
  cuotas: [],
  categoria: null,
  categoria_nueva: null,
  lugar_pago: 'agente',
}

function documento(propuesta: Propuesta | null = PROPUESTA): Documento {
  return {
    id: 'd1',
    estado: 'listo',
    tipo_archivo: 'image/png',
    nombre_archivo: 'recibo.png',
    tamano: 1000,
    paginas: 1,
    subido_en: '2026-10-21T10:00:00Z',
    analizado_en: '2026-10-21T10:00:03Z',
    riesgo: 'bajo',
    senales: [],
    propuesta,
    repetido_de: null,
    deuda_id: null,
  }
}

function montar(doc = documento(), rol: 'gerente' | 'asistente' = 'asistente') {
  return mount(FormularioDeuda, { props: { documento: doc, rol }, attachTo: document.body })
}

const campo = (formulario: ReturnType<typeof montar>, etiqueta: string) => {
  const label = formulario.findAll('label').find((l) => l.text().startsWith(etiqueta))
  return formulario.get(`#${label!.attributes('for')}`)
}

describe('FormularioDeuda', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useCategoriasStore().categorias = []
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('llena los campos con lo que se leyó del documento y los envía como texto', async () => {
    const fetch = simularFetch(respuesta(201, { deuda: {}, avisos: [] }))
    const formulario = montar()

    expect((campo(formulario, 'Concepto').element as HTMLInputElement).value).toBe(
      'Luz Hidrandina setiembre 2026',
    )
    await formulario.get('form').trigger('submit')
    await flushPromises()

    const cuerpo = JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))
    expect(cuerpo).toMatchObject({
      documento_id: 'd1',
      lugar_pago: 'agente',
      cuotas: [{ vence_el: '2026-10-28', importe: '182.40' }],
      codigo_pago: '54871236',
      categoria_id: null,
    })
    expect(formulario.emitted('registrada')).toHaveLength(1)
  })

  it('muestra junto a cada campo lo que falta según el backend', async () => {
    simularFetch(
      respuesta(422, {
        code: 'DATOS_INVALIDOS',
        detail: 'Revisa los datos marcados.',
        fields: {
          lugar_pago: 'Elige dónde se pagará esta deuda.',
          'cuotas.0.importe': 'Escribe el importe en soles.',
          'cuotas.0.vence_el': 'Indica la fecha de vencimiento.',
        },
      }),
    )
    const formulario = montar(documento(null))

    await formulario.get('form').trigger('submit')
    await flushPromises()

    expect(formulario.text()).toContain('Elige dónde se pagará esta deuda.')
    expect(formulario.text()).toContain('Escribe el importe en soles.')
    expect(formulario.text()).toContain('Indica la fecha de vencimiento.')
    expect(formulario.get('#vence-el').attributes('aria-invalid')).toBe('true')
    expect(formulario.emitted('registrada')).toBeUndefined()
  })

  it('avisa a la asistente que corregir el importe pide la autorización del gerente', async () => {
    const formulario = montar()
    expect(formulario.text()).not.toContain('deberá autorizar')

    await campo(formulario, 'Importe').setValue('82.40')

    expect(formulario.text()).toContain('tu gerente deberá autorizar esta deuda')
  })

  it('un cronograma abre las cuotas con sus importes distintos', () => {
    const formulario = montar(
      documento({
        ...PROPUESTA,
        tipo: 'cronograma',
        cuotas: [
          { numero: 1, vence_el: '2026-11-15', importe: '350.00' },
          { numero: 2, vence_el: '2026-12-15', importe: '362.75' },
        ],
      }),
    )

    expect(formulario.get('input[type="checkbox"]').element).toHaveProperty('checked', true)
    expect(formulario.text()).toContain('2 cuotas')
    expect(formulario.text()).toMatch(/S\/\s712\.75/)
  })

  it('sugiere crear la categoría que propuso el análisis o dejarla en Otros', async () => {
    const formulario = montar(
      documento({ ...PROPUESTA, tipo: 'papeleta', categoria_nueva: 'Papeletas' }),
    )

    expect(formulario.text()).toContain('Crea la categoría «Papeletas»')
    await formulario
      .findAll('button')
      .find((b) => b.text() === 'Omitir')!
      .trigger('click')
    expect(formulario.text()).not.toContain('Crea la categoría «Papeletas»')
  })
})
