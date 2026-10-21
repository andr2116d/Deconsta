export type TipoDocumentoTitular = 'dni' | 'ce' | 'ruc'

export interface Titular {
  id: string
  nombre: string
  relacion: string | null
  tipo_documento: TipoDocumentoTitular | null
  /** Enmascarado por el backend: «•••• 4568». */
  documento: string | null
  autorizacion_declarada_en: string
  creado_en: string
}

export interface Reglas {
  /** Texto con dos decimales («2900.00»); null: sin límite. */
  limite_importe: string | null
  actualizado_en: string | null
  titulares: Titular[]
  maximo_titulares: number
}

export interface NuevoTitular {
  nombre: string
  tipo_documento: TipoDocumentoTitular | null
  numero_documento: string | null
  relacion: string | null
  autorizacion_declarada: boolean
}

export interface EdicionTitular {
  nombre: string
  relacion: string | null
}

export interface DocumentoPorEvaluar {
  importe: string
  titular_nombre: string | null
}

export type CodigoMotivo = 'IMPORTE_SOBRE_LIMITE' | 'TITULAR_DISTINTO'

export interface Evaluacion {
  requiere_autorizacion: boolean
  motivos: Array<{ codigo: CodigoMotivo; detalle: string }>
  titular_reconocido: string | null
}
