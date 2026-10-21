import type { Sesion } from '@/features/acceso/types'
import { enviarJson, solicitar } from '@/shared/api/http'

import type { DocumentoAceptado, DocumentoLegal, Espacio } from '../types'

export const obtenerDocumentos = () => solicitar<DocumentoLegal[]>('/documentos-legales')

export const aceptarDocumentos = (documentos: DocumentoAceptado[]) =>
  enviarJson<Sesion>('/documentos-legales/aceptacion', { documentos })

export interface ConfirmacionDatos {
  nombres: string
  apellidos: string
  correo: string
  telefono: string
  tipo_documento: 'dni' | 'ce'
  numero_documento: string
}

export const confirmarDatos = (datos: ConfirmacionDatos) =>
  enviarJson<Sesion>('/cuenta/confirmacion-datos', datos)

/** Solo responde a cuentas con la incorporación completa: el backend lo comprueba. */
export const obtenerEspacio = () => solicitar<Espacio>('/espacio')
