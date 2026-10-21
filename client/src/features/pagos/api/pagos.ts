import { descargar, enviarFormulario, enviarJson, solicitar } from '@/shared/api/http'

import type {
  BloqueoPagos,
  Comprobante,
  DatosAMano,
  EstadoMora,
  EstadoPago,
  Mora,
  MoraDetalle,
  NuevaMora,
  NuevoPago,
  NuevoPedido,
  Pago,
  PagoDetalle,
  Pedido,
  PorPagar,
  Proposito,
} from '../types'

const comprobante = (id: string) => `/pagos/comprobantes/${encodeURIComponent(id)}`

export const listarPorPagar = () => solicitar<PorPagar>('/pagos/por-pagar')

/**
 * Sube el voucher de una cuota o, con el propósito mora, la prueba de su mora. El backend responde
 * «analizando» y lo compara con la cuota.
 */
export function subirComprobante(
  archivo: File,
  deudaId: string,
  cuota: number,
  proposito: Proposito = 'pago',
) {
  const datos = new FormData()
  datos.append('archivo', archivo, archivo.name)
  datos.append('deuda_id', deudaId)
  datos.append('cuota', String(cuota))
  datos.append('proposito', proposito)
  return enviarFormulario<Comprobante>('/pagos/comprobantes', datos)
}

export const consultarComprobante = (id: string) => solicitar<Comprobante>(comprobante(id))

/** Si la lectura automática falló, quien lo subió escribe sus datos; el gerente lo verá. */
export const completarComprobante = (id: string, datos: DatosAMano) =>
  enviarJson<Comprobante>(`${comprobante(id)}/datos`, datos)

/** El archivo descifrado, solo para quien lo subió y su gerente. */
export const descargarComprobante = (id: string) => descargar(`${comprobante(id)}/contenido`)

export const registrarPago = (datos: NuevoPago) => enviarJson<Pago>('/pagos', datos)

const pago = (id: string, accion = '') =>
  `/pagos/${encodeURIComponent(id)}${accion ? `/${accion}` : ''}`

export const listarPagos = (estado?: EstadoPago) =>
  solicitar<Pago[]>(estado ? `/pagos?estado=${estado}` : '/pagos')

export const consultarPago = (id: string) => solicitar<PagoDetalle>(pago(id))

export const confirmarPago = (id: string) => enviarJson<PagoDetalle>(pago(id, 'confirmacion'))

export const devolverPago = (id: string, motivo: string) =>
  enviarJson<PagoDetalle>(pago(id, 'devolucion'), { motivo })

export const listarBloqueosPagos = () => solicitar<BloqueoPagos[]>('/registro-pagos/bloqueos')

export const levantarBloqueoPagos = (asistenteId: string) =>
  enviarJson<void>(`/registro-pagos/bloqueos/${encodeURIComponent(asistenteId)}/levantamiento`)

const mora = (id: string, accion = '') =>
  `/pagos/moras/${encodeURIComponent(id)}${accion ? `/${accion}` : ''}`

export const declararMora = (datos: NuevaMora) => enviarJson<Mora>('/pagos/moras', datos)

export const listarMoras = (estado?: EstadoMora) =>
  solicitar<Mora[]>(estado ? `/pagos/moras?estado=${estado}` : '/pagos/moras')

export const consultarMora = (id: string) => solicitar<MoraDetalle>(mora(id))

export const aprobarMora = (id: string) => enviarJson<MoraDetalle>(mora(id, 'aprobacion'))

export const rechazarMora = (id: string, motivo: string) =>
  enviarJson<MoraDetalle>(mora(id, 'rechazo'), { motivo })

export const pedirPago = (datos: NuevoPedido) => enviarJson<Pedido>('/pagos/pedidos', datos)

/** Los pendientes: a una asistente, los suyos; al gerente, los de su espacio. */
export const listarPedidos = () => solicitar<Pedido[]>('/pagos/pedidos')

export const retirarPedido = (id: string) =>
  enviarJson<void>(`/pagos/pedidos/${encodeURIComponent(id)}/retiro`)
