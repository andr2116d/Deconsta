import { descargar, enviarFormulario, enviarJson, solicitar } from '@/shared/api/http'

import type { BloqueoPagos, Comprobante, NuevoPago, Pago, PorPagar } from '../types'

const comprobante = (id: string) => `/pagos/comprobantes/${encodeURIComponent(id)}`

export const listarPorPagar = () => solicitar<PorPagar>('/pagos/por-pagar')

/** Sube el voucher de una cuota; el backend responde «analizando» y lo compara con la cuota. */
export function subirComprobante(archivo: File, deudaId: string, cuota: number) {
  const datos = new FormData()
  datos.append('archivo', archivo, archivo.name)
  datos.append('deuda_id', deudaId)
  datos.append('cuota', String(cuota))
  return enviarFormulario<Comprobante>('/pagos/comprobantes', datos)
}

export const consultarComprobante = (id: string) => solicitar<Comprobante>(comprobante(id))

/** El archivo descifrado, solo para quien lo subió y su gerente. */
export const descargarComprobante = (id: string) => descargar(`${comprobante(id)}/contenido`)

export const registrarPago = (datos: NuevoPago) => enviarJson<Pago>('/pagos', datos)

export const listarPagos = () => solicitar<Pago[]>('/pagos')

export const listarBloqueosPagos = () => solicitar<BloqueoPagos[]>('/registro-pagos/bloqueos')

export const levantarBloqueoPagos = (asistenteId: string) =>
  enviarJson<void>(`/registro-pagos/bloqueos/${encodeURIComponent(asistenteId)}/levantamiento`)
