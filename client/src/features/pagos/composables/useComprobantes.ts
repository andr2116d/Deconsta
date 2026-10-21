import { computed, onBeforeUnmount, reactive } from 'vue'

import { errorArchivo } from '@/features/deudas/composables/useAnalisisDocumento'
import { ErrorApi } from '@/shared/api/http'

import { consultarComprobante, subirComprobante } from '../api/pagos'
import type { Comprobante, Proposito } from '../types'

export type EtapaVoucher = 'subiendo' | 'analizando' | 'terminado' | 'error'

export interface Voucher {
  clave: number
  archivo: File
  vista: string
  etapa: EtapaVoucher
  comprobante: Comprobante | null
  error: ErrorApi | null
  /** El análisis está tardando más de lo habitual. */
  demorado: boolean
}

/** Un agente puede cobrar por partes: hasta cinco vouchers por pago, como el backend. */
export const MAXIMO_VOUCHERS = 5
const INTERVALO_MS = 1200
const DEMORA_MS = 20_000
const ESPERA_MAXIMA_MS = 180_000

const espera = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms))
const aCentimos = (importe: string | null | undefined) =>
  Math.round(Number.parseFloat(importe ?? '0') * 100)

function errorDe(causa: unknown): ErrorApi {
  return causa instanceof ErrorApi
    ? causa
    : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
}

/**
 * Los vouchers de una cuota: cada uno se sube y se espera su análisis por separado. Quitar uno o
 * salir de la pantalla deja de esperarlo: su respuesta tardía nunca pisa a otro.
 */
export function useComprobantes(
  deudaId: () => string,
  cuota: () => number,
  proposito: Proposito = 'pago',
) {
  const vouchers = reactive<Voucher[]>([])
  const vigentes = new Set<number>()
  let siguiente = 0

  const buscar = (clave: number) => vouchers.find((v) => v.clave === clave)

  async function esperarAnalisis(clave: number, id: string) {
    const inicio = Date.now()
    while (vigentes.has(clave) && Date.now() - inicio < ESPERA_MAXIMA_MS) {
      await espera(INTERVALO_MS)
      const voucher = buscar(clave)
      if (!voucher || !vigentes.has(clave)) return
      voucher.demorado = Date.now() - inicio >= DEMORA_MS
      try {
        voucher.comprobante = await consultarComprobante(id)
      } catch (causa) {
        // Un corte de red o del servidor no pierde el voucher: se vuelve a consultar.
        const pasajero = causa instanceof ErrorApi && (causa.estado === 0 || causa.estado >= 500)
        if (pasajero) continue
        throw causa
      }
      if (voucher.comprobante.estado !== 'analizando') {
        voucher.etapa = 'terminado'
        return
      }
    }
    const voucher = buscar(clave)
    if (voucher && vigentes.has(clave)) {
      voucher.etapa = 'error'
      voucher.error = new ErrorApi(0, {
        code: 'ANALISIS_DEMORADO',
        detail: 'La revisión del voucher está tardando más de lo normal. Súbelo otra vez.',
      })
    }
  }

  async function agregar(archivo: File) {
    const clave = (siguiente += 1)
    vouchers.push({
      clave,
      archivo,
      vista: URL.createObjectURL(archivo),
      etapa: 'subiendo',
      comprobante: null,
      error: null,
      demorado: false,
    })
    vigentes.add(clave)
    const local = errorArchivo(archivo)
    const voucher = buscar(clave)!
    if (local) {
      voucher.etapa = 'error'
      voucher.error = new ErrorApi(422, { code: 'ARCHIVO_INVALIDO', detail: local })
      return
    }
    try {
      const subido = await subirComprobante(archivo, deudaId(), cuota(), proposito)
      if (!vigentes.has(clave)) return
      voucher.comprobante = subido
      voucher.etapa = subido.estado === 'analizando' ? 'analizando' : 'terminado'
      if (subido.estado === 'analizando') await esperarAnalisis(clave, subido.id)
    } catch (causa) {
      if (!vigentes.has(clave)) return
      voucher.etapa = 'error'
      voucher.error = errorDe(causa)
    }
  }

  function quitar(clave: number) {
    vigentes.delete(clave)
    const indice = vouchers.findIndex((v) => v.clave === clave)
    if (indice < 0) return
    URL.revokeObjectURL(vouchers[indice]!.vista)
    vouchers.splice(indice, 1)
  }

  /** El voucher que se completó a mano: el backend devuelve su comprobante listo. */
  function completar(clave: number, comprobante: Comprobante) {
    const voucher = buscar(clave)
    if (voucher) voucher.comprobante = comprobante
  }

  function reiniciar() {
    // Las claves primero: quitar cambia la lista mientras se recorre.
    for (const clave of vouchers.map((v) => v.clave)) quitar(clave)
  }

  const listos = computed(() => vouchers.filter((v) => v.comprobante?.estado === 'listo'))
  const trabajando = computed(() =>
    vouchers.some((v) => v.etapa === 'subiendo' || v.etapa === 'analizando'),
  )
  /** Lo que suman los vouchers listos, en céntimos: sin errores de coma flotante. */
  const sumaCentimos = computed(() =>
    listos.value.reduce((total, v) => total + aCentimos(v.comprobante?.lectura?.importe), 0),
  )
  const bloqueado = computed(() => vouchers.some((v) => v.comprobante?.registro_bloqueado))

  onBeforeUnmount(reiniciar)

  return {
    vouchers,
    listos,
    trabajando,
    sumaCentimos,
    bloqueado,
    agregar,
    quitar,
    completar,
    reiniciar,
  }
}

export { aCentimos }
