/**
 * Importes en soles mientras se escriben. Solo orientan: el backend valida el importe y decide.
 * Se envían como texto («2900.50»), nunca como número de coma flotante.
 */

// 7 dígitos enteros (hasta S/ 9,999,999.99) más dos comas de miles.
const MAXIMO_PARTE_ENTERA = 9

const soles = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' })

/** «S/ 2,900.50», como se lee en Perú. */
export const formatearSoles = (importe: string | number) => soles.format(Number(importe))

/**
 * Dígitos, comas y un solo punto decimal con hasta dos decimales. Las comas se conservan tal como
 * se escriben o pegan («2,900.50»); al enviar se interpretan con normalizarImporte.
 */
export function filtrarImporte(valor: string): string {
  const [enteros = '', ...decimales] = valor.replace(/[^\d.,]/g, '').split('.')
  const parteEntera = enteros.replace(/^0+(?=\d)/, '').slice(0, MAXIMO_PARTE_ENTERA)
  if (!decimales.length) return parteEntera
  return `${parteEntera || '0'}.${decimales.join('').replace(/,/g, '').slice(0, 2)}`
}

/**
 * Forma que se envía («2900.50»). En Perú la coma separa los miles («2,900.50»); solo se toma como
 * decimal si no hay punto y le siguen uno o dos dígitos al final («2900,5»).
 */
export function normalizarImporte(valor: string): string {
  let importe = valor.trim()
  if (!importe.includes('.') && !/^\d{1,3}(,\d{3})+$/.test(importe)) {
    importe = importe.replace(/,(?=\d{1,2}$)/, '.')
  }
  return importe.replace(/,/g, '').replace(/\.$/, '')
}

export function avisoImporte(valor: string): string | undefined {
  if (!valor) return undefined
  const importe = normalizarImporte(valor)
  if (!importe || Number(importe) <= 0) return 'El importe debe ser mayor que cero.'
  if ((importe.split('.')[0] ?? '').length > 7)
    return 'El importe no puede superar S/ 9,999,999.99.'
  if (valor.includes(',')) return `Se guardará como ${formatearSoles(importe)}.`
  return undefined
}
