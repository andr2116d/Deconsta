export type TipoDocumentoLegal = 'terminos' | 'privacidad'

export interface Seccion {
  titulo: string
  parrafos: string[]
}

export interface DocumentoLegal {
  tipo: TipoDocumentoLegal
  version: number
  titulo: string
  resumen: string
  secciones: Seccion[]
  vigente_desde: string
  aceptado_en: string | null
}

export interface DocumentoAceptado {
  tipo: TipoDocumentoLegal
  version: number
}

export interface Espacio {
  disponible: boolean
}
