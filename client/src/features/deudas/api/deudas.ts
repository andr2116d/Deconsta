import { descargar, enviarFormulario, enviarJson, solicitar } from '@/shared/api/http'

import type {
  BloqueoRegistro,
  Deuda,
  DeudaDetalle,
  Documento,
  NuevaDeuda,
  RegistroDeuda,
} from '../types'

const documento = (id: string) => `/documentos/${encodeURIComponent(id)}`
const deuda = (id: string, accion = '') =>
  `/deudas/${encodeURIComponent(id)}${accion ? `/${accion}` : ''}`

/** Sube el documento; el backend responde «analizando» y lo analiza en segundo plano. */
export function subirDocumento(archivo: File): Promise<Documento> {
  const datos = new FormData()
  datos.append('archivo', archivo, archivo.name)
  return enviarFormulario<Documento>('/documentos', datos)
}

export const consultarDocumento = (id: string) => solicitar<Documento>(documento(id))

/** El archivo descifrado, solo para quien lo subió y su gerente. */
export const descargarDocumento = (id: string) => descargar(`${documento(id)}/contenido`)

export const registrarDeuda = (datos: NuevaDeuda) => enviarJson<RegistroDeuda>('/deudas', datos)

export const listarPendientes = () => solicitar<Deuda[]>('/deudas?pendientes=true')

export const consultarDeuda = (id: string) => solicitar<DeudaDetalle>(deuda(id))

export const autorizarDeuda = (id: string) => enviarJson<DeudaDetalle>(deuda(id, 'autorizacion'))

export const rechazarDeuda = (id: string, motivo: string) =>
  enviarJson<DeudaDetalle>(deuda(id, 'rechazo'), { motivo })

export const darVistoBueno = (id: string) => enviarJson<DeudaDetalle>(deuda(id, 'revision'))

export const anularDeuda = (id: string, motivo: string) =>
  enviarJson<DeudaDetalle>(deuda(id, 'anulacion'), { motivo })

export const listarBloqueos = () => solicitar<BloqueoRegistro[]>('/registro-deudas/bloqueos')

export const levantarBloqueo = (asistenteId: string) =>
  enviarJson<void>(`/registro-deudas/bloqueos/${encodeURIComponent(asistenteId)}/levantamiento`)
