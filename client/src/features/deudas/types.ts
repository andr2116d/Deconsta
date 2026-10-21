import type { TipoDocumentoTitular } from '@/features/reglas/types'

export type EstadoDocumento =
  'analizando' | 'listo' | 'ilegible' | 'repetido' | 'rechazado' | 'fallido'

export type TipoDocumento =
  'recibo_servicio' | 'boleta' | 'factura' | 'cronograma' | 'papeleta' | 'tributo' | 'otro'

export type Riesgo = 'bajo' | 'medio' | 'alto'

export type LugarPago =
  'ventanilla' | 'agente' | 'banca_digital' | 'transferencia' | 'billetera' | 'debito_automatico'

export type EstadoDeuda = 'por_autorizar' | 'registrada' | 'rechazada' | 'anulada'

export type MotivoEspera =
  'IMPORTE_SOBRE_LIMITE' | 'TITULAR_DISTINTO' | 'DOCUMENTO_DUDOSO' | 'DATOS_CORREGIDOS'

/** Capa del análisis que encontró algo. */
export type Capa = 'lectura' | 'ia' | 'metadatos'

export interface Senal {
  capa: Capa
  codigo: string
  detalle: string
  riesgo: Riesgo
}

export interface CuotaPropuesta {
  numero: number
  vence_el: string
  importe: string
}

/** Lo que se leyó del documento. Es una propuesta: quien registra la revisa. */
export interface Propuesta {
  tipo: TipoDocumento
  concepto: string | null
  emisor: string | null
  titular_nombre: string | null
  titular_tipo_documento: TipoDocumentoTitular | null
  titular_numero_documento: string | null
  codigo_pago: string | null
  numero_documento: string | null
  periodo: string | null
  importe: string | null
  vence_el: string | null
  cuotas: CuotaPropuesta[]
  /** Nombre de una categoría del espacio, o el de una nueva que convendría crear. */
  categoria: string | null
  categoria_nueva: string | null
  lugar_pago: LugarPago | null
}

export interface DeudaDelDocumento {
  id: string
  concepto: string
  registrada_en: string
}

export interface Documento {
  id: string
  estado: EstadoDocumento
  tipo_archivo: string
  nombre_archivo: string
  tamano: number
  paginas: number
  subido_en: string
  analizado_en: string | null
  riesgo: Riesgo | null
  senales: Senal[]
  propuesta: Propuesta | null
  repetido_de: DeudaDelDocumento | null
  deuda_id: string | null
}

export interface Cuota {
  numero: number
  vence_el: string
  importe: string
}

export interface Deuda {
  id: string
  documento_id: string
  concepto: string
  categoria_id: string | null
  tipo_documento: TipoDocumento
  importe: string
  vence_el: string
  cuotas: Cuota[]
  lugar_pago: LugarPago
  titular_nombre: string | null
  titular_tipo_documento: TipoDocumentoTitular | null
  /** Enmascarado por el backend: «•••• 8912». */
  titular_documento: string | null
  codigo_pago: string | null
  estado: EstadoDeuda
  motivos: MotivoEspera[]
  revision_pendiente: boolean
  campos_corregidos: string[]
  registrada_por: { id: string; nombre: string }
  creado_en: string
  decidida_en: string | null
  motivo_decision: string | null
}

export interface DeudaDetalle extends Deuda {
  documento: Documento | null
}

export interface RegistroDeuda {
  deuda: Deuda
  /** Lo que se le advierte al gerente cuando registra él mismo. */
  avisos: string[]
}

export interface CuotaNueva {
  vence_el: string
  /** En soles, como texto («182.40»). */
  importe: string
}

export interface NuevaDeuda {
  documento_id: string
  concepto: string
  categoria_id: string | null
  lugar_pago: LugarPago | null
  cuotas: CuotaNueva[]
  titular_nombre: string | null
  titular_tipo_documento: TipoDocumentoTitular | null
  titular_numero_documento: string | null
  codigo_pago: string | null
}

/** Deuda que ya usa un documento, en DOCUMENTO_YA_REGISTRADO. */
export interface DeudaExistente {
  id: string
  concepto: string
  registrada_en: string
}

export interface BloqueoRegistro {
  asistente_id: string
  bloqueado_en: string
}
