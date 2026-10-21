import { describe, expect, it } from 'vitest'

import { cuandoVence, esDia, semanasDelMes, sumarDias, sumarMeses } from '../fechas'

describe('fechas del calendario', () => {
  it('muestra el mes en seis semanas que empiezan en lunes', () => {
    const semanas = semanasDelMes('2026-10')

    // El 1 de octubre de 2026 es jueves.
    expect(semanas[0]).toEqual([
      '2026-09-28',
      '2026-09-29',
      '2026-09-30',
      '2026-10-01',
      '2026-10-02',
      '2026-10-03',
      '2026-10-04',
    ])
    expect(semanas).toHaveLength(6)
    expect(semanas.flat()).toContain('2026-10-31')
  })

  it('cruza meses y años sin perder días', () => {
    expect(sumarDias('2026-12-31', 1)).toBe('2027-01-01')
    expect(sumarDias('2028-03-01', -1)).toBe('2028-02-29')
    expect(sumarMeses('2026-01', -1)).toBe('2025-12')
    expect(sumarMeses('2026-12', 1)).toBe('2027-01')
  })

  it('dice con palabras cuándo vence', () => {
    expect(cuandoVence('2026-10-21', '2026-10-21')).toBe('Vence hoy')
    expect(cuandoVence('2026-10-22', '2026-10-21')).toBe('Vence mañana')
    expect(cuandoVence('2026-10-26', '2026-10-21')).toBe('Vence en 5 días')
    expect(cuandoVence('2026-10-20', '2026-10-21')).toBe('Venció ayer')
    expect(cuandoVence('2026-10-11', '2026-10-21')).toBe('Venció hace 10 días')
  })

  it('no acepta días que no existen en la dirección', () => {
    expect(esDia('2026-02-30')).toBe(false)
    expect(esDia('2026-10-21')).toBe(true)
    expect(esDia(['2026-10-21'])).toBe(false)
  })
})
