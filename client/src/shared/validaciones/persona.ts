/**
 * Filtros y avisos de los datos personales. Los filtros impiden escribir lo que nunca sería válido
 * (letras en un DNI, más de 9 dígitos en un celular) y los avisos dicen, mientras se escribe, qué
 * falta. Solo orientan: el backend aplica las mismas reglas y es la autoridad.
 *
 * - DNI: 8 dígitos (RENIEC).
 * - Carné de extranjería: de 9 a 12 letras o dígitos (Migraciones emite 9 dígitos; se admiten
 *   carnés antiguos alfanuméricos de hasta 12).
 * - Celular peruano: 9 dígitos que empiezan con 9 (plan de numeración del MTC); +51 es el código
 *   del país y no se escribe.
 * - Correo: usuario, @ y dominio con extensión.
 */

export type TipoDocumento = 'dni' | 'ce'

export const LONGITUD_DNI = 8
export const LONGITUD_CELULAR = 9
export const CARNE = { minimo: 9, maximo: 12 } as const

/** Letras (con tildes y ñ), espacios, apóstrofo, punto y guion. */
export const filtrarNombre = (valor: string) => valor.replace(/[^\p{L} '’.-]/gu, '')

export const filtrarDni = (valor: string) => valor.replace(/\D/g, '').slice(0, LONGITUD_DNI)

export const filtrarCarne = (valor: string) =>
  valor
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
    .slice(0, CARNE.maximo)

export const filtrarDocumento = (tipo: TipoDocumento) =>
  tipo === 'dni' ? filtrarDni : filtrarCarne

/** Solo dígitos; si se pega con el código del país (+51 987…), se quita. */
export function filtrarCelular(valor: string): string {
  let digitos = valor.replace(/\D/g, '')
  if (digitos.length > LONGITUD_CELULAR && digitos.startsWith('51')) digitos = digitos.slice(2)
  return digitos.slice(0, LONGITUD_CELULAR)
}

/** Sin espacios: un correo no los lleva. */
export const filtrarCorreo = (valor: string) => valor.replace(/\s/g, '')

const faltan = (n: number, singular: string, plural: string) =>
  n === 1 ? `Falta 1 ${singular}.` : `Faltan ${n} ${plural}.`

export function avisoDocumento(tipo: TipoDocumento, valor: string): string | undefined {
  if (!valor) return undefined
  if (tipo === 'dni') {
    return valor.length < LONGITUD_DNI
      ? `El DNI tiene ${LONGITUD_DNI} dígitos. ${faltan(LONGITUD_DNI - valor.length, 'dígito', 'dígitos')}`
      : undefined
  }
  if (valor.length >= CARNE.minimo) return undefined
  const resta = faltan(CARNE.minimo - valor.length, 'carácter', 'caracteres')
  return `El carné tiene de ${CARNE.minimo} a ${CARNE.maximo} letras o dígitos. ${resta}`
}

export function avisoCelular(valor: string): string | undefined {
  if (!valor) return undefined
  if (!valor.startsWith('9')) return 'Un celular peruano empieza con 9.'
  if (valor.length < LONGITUD_CELULAR) {
    return faltan(LONGITUD_CELULAR - valor.length, 'dígito', 'dígitos')
  }
  return undefined
}

export function avisoCorreo(valor: string): string | undefined {
  if (!valor) return undefined
  const [usuario, dominio, ...resto] = valor.split('@')
  if (dominio === undefined) return 'Incluye la @, por ejemplo nombre@empresa.pe.'
  if (resto.length) return 'Un correo lleva una sola @.'
  if (!usuario) return 'Escribe tu usuario antes de la @.'
  if (!/^[^.]+(\.[^.]+)*\.[a-z]{2,}$/i.test(dominio)) {
    return 'Completa el dominio con su extensión, por ejemplo empresa.pe.'
  }
  return undefined
}

export const celularValido = (valor: string) => /^9\d{8}$/.test(valor)
export const documentoValido = (tipo: TipoDocumento, valor: string) =>
  tipo === 'dni' ? /^\d{8}$/.test(valor) : /^[A-Z0-9]{9,12}$/.test(valor)
export const correoValido = (valor: string) => !!valor && avisoCorreo(valor) === undefined
