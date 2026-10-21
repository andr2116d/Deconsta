import { describe, expect, it } from 'vitest'

import { cuotasMensuales, cuotasPropuestas, sumarMeses, totalCuotas } from '../cuotas'
import type { Propuesta } from '../types'

describe('cuotas', () => {
  it('suma en céntimos, sin errores de coma flotante', () => {
    const cuotas = [
      { vence_el: '2026-11-15', importe: '0.10' },
      { vence_el: '2026-12-15', importe: '0.20' },
      { vence_el: '2027-01-15', importe: '1,000.05' },
    ]
    expect(totalCuotas(cuotas)).toBe('1000.35')
    expect(totalCuotas([{ vence_el: '', importe: 'abc' }])).toBeNull()
  })

  it('en los meses cortos pasa al último día', () => {
    expect(sumarMeses('2027-01-31', 1)).toBe('2027-02-28')
    expect(sumarMeses('2028-01-31', 1)).toBe('2028-02-29')
    expect(sumarMeses('2026-12-15', 2)).toBe('2027-02-15')
  })

  it('genera cuotas mensuales iguales que luego se ajustan', () => {
    const cuotas = cuotasMensuales(3, '350.00', '2026-11-30')
    expect(cuotas.map((c) => c.vence_el)).toEqual(['2026-11-30', '2026-12-30', '2027-01-30'])
    expect(new Set(cuotas.map((c) => c.importe))).toEqual(new Set(['350.00']))
  })

  it('propone las cuotas del cronograma o una sola con el importe leído', () => {
    const base = { cuotas: [], importe: '182.40', vence_el: '2026-10-28' } as unknown as Propuesta
    expect(cuotasPropuestas(base)).toEqual([{ vence_el: '2026-10-28', importe: '182.40' }])
    const cronograma = {
      ...base,
      cuotas: [
        { numero: 1, vence_el: '2026-11-15', importe: '350.00' },
        { numero: 2, vence_el: '2026-12-15', importe: '362.75' },
      ],
    }
    expect(cuotasPropuestas(cronograma).map((c) => c.importe)).toEqual(['350.00', '362.75'])
    expect(cuotasPropuestas(null)).toEqual([{ vence_el: '', importe: '' }])
  })
})
