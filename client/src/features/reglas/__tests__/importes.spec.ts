import { describe, expect, it } from 'vitest'

import { avisoImporte, filtrarImporte, formatearSoles, normalizarImporte } from '../importes'

describe('importes en soles', () => {
  it('no deja escribir lo que nunca sería un importe', () => {
    expect(filtrarImporte('S/ 2,900.555')).toBe('2,900.55')
    expect(filtrarImporte('00150')).toBe('150')
    expect(filtrarImporte('1234567890')).toBe('123456789')
  })

  it('envía el importe con punto decimal y lo muestra como se lee en Perú', () => {
    // En Perú la coma separa los miles; sola y con uno o dos dígitos, es decimal.
    expect(normalizarImporte('2,900.50')).toBe('2900.50')
    expect(normalizarImporte('2,900')).toBe('2900')
    expect(normalizarImporte('2900,5')).toBe('2900.5')
    expect(normalizarImporte('2900.')).toBe('2900')
    // Intl separa «S/» con un espacio que no se corta.
    expect(formatearSoles('2900.5').replace(/\s/g, ' ')).toBe('S/ 2,900.50')
    expect(avisoImporte('0.00')).toBe('El importe debe ser mayor que cero.')
    expect(avisoImporte('12345678')).toContain('no puede superar')
    expect(avisoImporte('2,900')?.replace(/\s/g, ' ')).toBe('Se guardará como S/ 2,900.00.')
  })
})
