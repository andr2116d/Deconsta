import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfirmacionRegistro from '../components/ConfirmacionRegistro.vue'
import type { Deuda } from '../types'

const DEUDA: Deuda = {
  id: 'x1',
  documento_id: 'd1',
  concepto: 'Luz de la casa',
  categoria_id: null,
  tipo_documento: 'recibo_servicio',
  importe: '182.40',
  vence_el: '2026-10-10',
  cuotas: [{ numero: 1, vence_el: '2026-10-10', importe: '182.40', pago: null }],
  lugares_pago: ['agente', 'billetera'],
  titular_nombre: null,
  titular_tipo_documento: null,
  titular_documento: null,
  codigo_pago: null,
  estado: 'registrada',
  motivos: [],
  revision_pendiente: true,
  campos_corregidos: [],
  registrada_por: { id: 'a1', nombre: 'Lucía Vega' },
  creado_en: '2026-10-21T10:00:00Z',
  decidida_en: null,
  motivo_decision: null,
  vencida_hace: 11,
}

const montar = (deuda: Deuda) =>
  mount(ConfirmacionRegistro, {
    props: { registro: { deuda, avisos: [] }, rol: 'asistente' },
    global: { stubs: { RouterLink: true } },
  })

describe('ConfirmacionRegistro', () => {
  it('una deuda vencida dice desde cuándo y sugiere revisar la mora antes de pagarla', () => {
    const confirmacion = montar(DEUDA)

    expect(confirmacion.text()).toContain('Venció hace 11 días')
    expect(confirmacion.text()).toContain('si cobra mora')
  })

  it('una deuda al día no habla de mora', () => {
    const confirmacion = montar({ ...DEUDA, vence_el: '2026-10-28', vencida_hace: null })

    expect(confirmacion.text()).toContain('Vence el')
    expect(confirmacion.text()).not.toContain('mora')
  })
})
