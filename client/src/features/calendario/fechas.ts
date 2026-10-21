/**
 * Días del calendario como texto «AAAA-MM-DD». Las cuentas se hacen en UTC para que el huso del
 * navegador no corra un día ni el cambio de horario deje uno repetido.
 */

import type { Dia, Mes } from './types'

const MS_DIA = 86_400_000

const aFecha = (dia: Dia) => new Date(`${dia}T00:00:00Z`)
const aDia = (fecha: Date): Dia => fecha.toISOString().slice(0, 10)
const dos = (n: number) => String(n).padStart(2, '0')

export const sumarDias = (dia: Dia, dias: number): Dia =>
  aDia(new Date(aFecha(dia).getTime() + dias * MS_DIA))

/** Días de `desde` a `hasta`: negativo si `hasta` es anterior. */
export const diasEntre = (desde: Dia, hasta: Dia) =>
  Math.round((aFecha(hasta).getTime() - aFecha(desde).getTime()) / MS_DIA)

export const mesDe = (dia: Dia): Mes => dia.slice(0, 7)

export function sumarMeses(mes: Mes, meses: number): Mes {
  const [anio = 0, numero = 1] = mes.split('-').map(Number)
  return aDia(new Date(Date.UTC(anio, numero - 1 + meses, 1))).slice(0, 7)
}

/** El día de hoy en el navegador, hasta que el backend diga el suyo. */
export function hoyLocal(): Dia {
  const ahora = new Date()
  return `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}-${dos(ahora.getDate())}`
}

export const esMes = (valor: unknown): valor is Mes =>
  typeof valor === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(valor)

export const esDia = (valor: unknown): valor is Dia =>
  typeof valor === 'string' &&
  /^\d{4}-\d{2}-\d{2}$/.test(valor) &&
  !Number.isNaN(aFecha(valor).getTime()) &&
  aDia(aFecha(valor)) === valor

/** Las seis semanas, de lunes a domingo, que muestran el mes completo. */
export function semanasDelMes(mes: Mes): Dia[][] {
  const primero = `${mes}-01`
  const desdeLunes = (aFecha(primero).getUTCDay() + 6) % 7
  const inicio = sumarDias(primero, -desdeLunes)
  return Array.from({ length: 6 }, (_, semana) =>
    Array.from({ length: 7 }, (_, dia) => sumarDias(inicio, semana * 7 + dia)),
  )
}

export const numeroDia = (dia: Dia) => aFecha(dia).getUTCDate()

const formato = (opciones: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat('es-PE', { ...opciones, timeZone: 'UTC' })
const mesLargo = formato({ month: 'long', year: 'numeric' })
const diaLargo = formato({ weekday: 'long', day: 'numeric', month: 'long' })
const diaSemana = formato({ weekday: 'long' })
const diaMes = formato({ day: 'numeric', month: 'long' })

const mayuscula = (texto: string) => texto.charAt(0).toUpperCase() + texto.slice(1)

/** «Octubre de 2026». */
export const nombreMes = (mes: Mes) => mayuscula(mesLargo.format(aFecha(`${mes}-01`)))

/** «miércoles, 21 de octubre». */
export const fechaLarga = (dia: Dia) => diaLargo.format(aFecha(dia))

/** «Miércoles» y «21 de octubre», para el encabezado del día. */
export const partesDia = (dia: Dia) => ({
  semana: mayuscula(diaSemana.format(aFecha(dia))),
  fecha: diaMes.format(aFecha(dia)),
})

/** Cuán cerca está un vencimiento: lo que vence en tres días o menos ya apura. */
export type Cercania = 'pasado' | 'hoy' | 'pronto' | 'despues'

export function cercania(dia: Dia, hoy: Dia): Cercania {
  const dias = diasEntre(hoy, dia)
  if (dias < 0) return 'pasado'
  if (dias === 0) return 'hoy'
  return dias <= 3 ? 'pronto' : 'despues'
}

/** «Vence hoy», «Vence mañana», «Vence en 5 días», «Venció ayer», «Venció hace 3 días». */
export function cuandoVence(dia: Dia, hoy: Dia): string {
  const dias = diasEntre(hoy, dia)
  if (dias === 0) return 'Vence hoy'
  if (dias === 1) return 'Vence mañana'
  if (dias === -1) return 'Venció ayer'
  return dias > 0 ? `Vence en ${dias} días` : `Venció hace ${-dias} días`
}
