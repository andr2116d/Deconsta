/**
 * Cuotas de una deuda mientras se arman. Solo ayudan a llenar el formulario: el backend valida
 * cada importe, el orden de las fechas y el total. Los importes se suman en céntimos, nunca con
 * números de coma flotante.
 */
import { normalizarImporte } from '@/features/reglas/importes'

import type { CuotaNueva, Propuesta } from './types'

export const MAXIMO_CUOTAS = 360

const centimos = (importe: string): number | null => {
  const limpio = normalizarImporte(importe)
  if (!/^\d{1,7}(\.\d{1,2})?$/.test(limpio)) return null
  const [enteros = '0', decimales = ''] = limpio.split('.')
  return Number(enteros) * 100 + Number(decimales.padEnd(2, '0'))
}

const aTexto = (centavos: number) =>
  `${Math.floor(centavos / 100)}.${String(centavos % 100).padStart(2, '0')}`

/** Total de las cuotas escritas, o null si alguna aún no es un importe. */
export function totalCuotas(cuotas: readonly CuotaNueva[]): string | null {
  let total = 0
  for (const cuota of cuotas) {
    const valor = centimos(cuota.importe)
    if (valor === null) return null
    total += valor
  }
  return aTexto(total)
}

/** El mismo día de cada mes; en los meses cortos, su último día (31 de enero → 28 de febrero). */
export function sumarMeses(dia: string, meses: number): string {
  const [anio = 0, mes = 1, numero = 1] = dia.split('-').map(Number)
  const destino = new Date(Date.UTC(anio, mes - 1 + meses, 1))
  const ultimo = new Date(
    Date.UTC(destino.getUTCFullYear(), destino.getUTCMonth() + 1, 0),
  ).getUTCDate()
  destino.setUTCDate(Math.min(numero, ultimo))
  return destino.toISOString().slice(0, 10)
}

/** Cuotas mensuales iguales desde una fecha, para luego ajustar las que cambian. */
export function cuotasMensuales(cantidad: number, importe: string, primera: string): CuotaNueva[] {
  const total = Math.max(1, Math.min(MAXIMO_CUOTAS, Math.trunc(cantidad)))
  return Array.from({ length: total }, (_, i) => ({
    vence_el: primera ? sumarMeses(primera, i) : '',
    importe,
  }))
}

/** Las cuotas que leyó el análisis o, si no es un cronograma, una sola con su importe. */
export function cuotasPropuestas(propuesta: Propuesta | null): CuotaNueva[] {
  if (propuesta?.cuotas.length) {
    return propuesta.cuotas.map((c) => ({ vence_el: c.vence_el, importe: c.importe }))
  }
  return [{ vence_el: propuesta?.vence_el ?? '', importe: propuesta?.importe ?? '' }]
}
