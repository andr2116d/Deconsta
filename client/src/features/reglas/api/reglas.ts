import { enviarJson, solicitar } from '@/shared/api/http'

import type {
  DocumentoPorEvaluar,
  EdicionTitular,
  Evaluacion,
  NuevoTitular,
  Reglas,
  Titular,
} from '../types'

const titular = (id: string, accion: string) =>
  `/reglas/titulares/${encodeURIComponent(id)}/${accion}`

export const consultarReglas = () => solicitar<Reglas>('/reglas')

/** Con un importe fija el límite; con null lo quita. */
export const cambiarLimite = (limite: string | null) =>
  enviarJson<Reglas>('/reglas/limite', { limite_importe: limite })

export const agregarTitular = (nuevo: NuevoTitular) =>
  enviarJson<Titular>('/reglas/titulares', nuevo)

export const editarTitular = (id: string, datos: EdicionTitular) =>
  enviarJson<Titular>(titular(id, 'edicion'), datos)

export const quitarTitular = (id: string, motivo: string | null) =>
  enviarJson<void>(titular(id, 'eliminacion'), { motivo })

export const evaluarDocumento = (documento: DocumentoPorEvaluar) =>
  enviarJson<Evaluacion>('/reglas/evaluacion', documento)
