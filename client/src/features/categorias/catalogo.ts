import type { Categoria, ColorCategoria, DatosCategoria, IconoCategoria } from './types'

/**
 * Catálogos de color e ícono (los mismos que acepta el backend) y ayudas para escribir el nombre.
 * Las reglas definitivas viven en el backend: aquí solo se avisa antes de enviar.
 */

export const LARGO_MINIMO_NOMBRE = 2
export const LARGO_MAXIMO_NOMBRE = 40
export const LARGO_MAXIMO_DESCRIPCION = 200

/** Tinta sobre su fondo con contraste suficiente para el ícono (≥ 3:1). */
export const COLORES: Record<ColorCategoria, { nombre: string; tinta: string; fondo: string }> = {
  ciruela: { nombre: 'Ciruela', tinta: '#6b304f', fondo: '#f1dde7' },
  coral: { nombre: 'Coral', tinta: '#a3412d', fondo: '#fbe4dd' },
  ambar: { nombre: 'Ámbar', tinta: '#885d16', fondo: '#fff3d8' },
  oliva: { nombre: 'Oliva', tinta: '#56631c', fondo: '#eef2d9' },
  verde: { nombre: 'Verde', tinta: '#286849', fondo: '#e6f2eb' },
  azul: { nombre: 'Azul', tinta: '#2d5a8a', fondo: '#e1ebf6' },
  lavanda: { nombre: 'Lavanda', tinta: '#5b4a9a', fondo: '#ebe7f7' },
  grafito: { nombre: 'Grafito', tinta: '#4a4550', fondo: '#ecebee' },
}

export const ICONOS: Record<IconoCategoria, string> = {
  agua: 'Agua',
  luz: 'Luz',
  gas: 'Gas',
  telefono: 'Teléfono',
  internet: 'Internet',
  tarjeta: 'Tarjeta',
  banco: 'Banco o préstamo',
  impuestos: 'Impuestos',
  vivienda: 'Vivienda',
  transporte: 'Transporte',
  salud: 'Salud',
  educacion: 'Educación',
  seguro: 'Seguro',
  etiqueta: 'Otros',
}

/** Punto de partida para un espacio nuevo: se crean solo si el gerente las elige. */
export const SUGERENCIAS: readonly DatosCategoria[] = [
  {
    nombre: 'Agua',
    descripcion: 'Recibos del servicio de agua y desagüe.',
    color: 'azul',
    icono: 'agua',
  },
  { nombre: 'Luz', descripcion: 'Recibos de electricidad.', color: 'ambar', icono: 'luz' },
  { nombre: 'Gas', descripcion: 'Gas natural o balones de gas.', color: 'coral', icono: 'gas' },
  {
    nombre: 'Telefonía e internet',
    descripcion: 'Planes de celular, telefonía fija, internet y cable.',
    color: 'lavanda',
    icono: 'internet',
  },
  {
    nombre: 'Tarjetas de crédito',
    descripcion: 'Estados de cuenta de tarjetas de crédito.',
    color: 'ciruela',
    icono: 'tarjeta',
  },
  {
    nombre: 'Préstamos',
    descripcion: 'Cuotas de préstamos y créditos.',
    color: 'grafito',
    icono: 'banco',
  },
  {
    nombre: 'Impuestos',
    descripcion: 'Tributos, arbitrios y predial.',
    color: 'oliva',
    icono: 'impuestos',
  },
  {
    nombre: 'Otros',
    descripcion: 'Lo que no encaja en otra categoría.',
    color: 'verde',
    icono: 'etiqueta',
  },
]

/** Forma para comparar nombres, igual que el backend: sin mayúsculas, tildes ni espacios extra. */
export function claveNombre(nombre: string): string {
  return nombre
    .normalize('NFKC')
    .trim()
    .split(/\s+/)
    .join(' ')
    .toLocaleLowerCase('es')
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
}

/** Lo que nunca sería válido no llega a escribirse: letras, números, espacios y . , & / ( ) ' + - */
export function filtrarNombreCategoria(valor: string): string {
  return valor
    .replace(/[^\p{L}\p{N} .,&/()'+-]/gu, '')
    .replace(/^[^\p{L}\p{N}]+/u, '')
    .replace(/ {2,}/g, ' ')
    .slice(0, LARGO_MAXIMO_NOMBRE)
}

/** Indicación mientras se escribe. */
export function avisoNombre(
  nombre: string,
  existentes: readonly Categoria[],
  propia?: string,
): string | undefined {
  const limpio = nombre.trim()
  if (!limpio) return undefined
  if (limpio.length < LARGO_MINIMO_NOMBRE) return `Usa al menos ${LARGO_MINIMO_NOMBRE} caracteres.`
  if (!/\p{L}/u.test(limpio)) return 'Incluye al menos una letra.'
  const igual = existentes.find(
    (c) => c.id !== propia && claveNombre(c.nombre) === claveNombre(limpio),
  )
  if (igual) {
    return igual.archivada
      ? `Ya tienes «${igual.nombre}» archivada: puedes reactivarla.`
      : `Ya tienes una categoría llamada «${igual.nombre}».`
  }
  return undefined
}
