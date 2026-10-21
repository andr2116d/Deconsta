export type ColorCategoria =
  'ciruela' | 'coral' | 'ambar' | 'oliva' | 'verde' | 'azul' | 'lavanda' | 'grafito'

export type IconoCategoria =
  | 'agua'
  | 'luz'
  | 'gas'
  | 'telefono'
  | 'internet'
  | 'tarjeta'
  | 'banco'
  | 'impuestos'
  | 'vivienda'
  | 'transporte'
  | 'salud'
  | 'educacion'
  | 'seguro'
  | 'etiqueta'

export interface Categoria {
  id: string
  nombre: string
  descripcion: string | null
  color: ColorCategoria
  icono: IconoCategoria
  archivada: boolean
  creado_en: string
  actualizado_en: string
  archivado_en: string | null
}

export interface DatosCategoria {
  nombre: string
  descripcion: string | null
  color: ColorCategoria
  icono: IconoCategoria
}

/** Categoría con el mismo nombre que devuelve el backend en CATEGORIA_DUPLICADA. */
export interface CategoriaExistente {
  id: string
  archivada: boolean
}
