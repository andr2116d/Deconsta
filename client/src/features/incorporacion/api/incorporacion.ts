import type { Sesion } from '@/features/acceso/types'
import { enviarJson, solicitar } from '@/shared/api/http'

import type { DocumentoAceptado, DocumentoLegal, Espacio } from '../types'

export const obtenerDocumentos = () => solicitar<DocumentoLegal[]>('/documentos-legales')

export const aceptarDocumentos = (documentos: DocumentoAceptado[]) =>
  enviarJson<Sesion>('/documentos-legales/aceptacion', { documentos })

/** Solo responde a cuentas con la incorporación completa: el backend lo comprueba. */
export const obtenerEspacio = () => solicitar<Espacio>('/espacio')
