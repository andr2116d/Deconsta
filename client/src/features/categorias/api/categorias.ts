import { enviarJson, solicitar } from '@/shared/api/http'

import type { Categoria, DatosCategoria } from '../types'

const ruta = (id: string, accion: string) => `/categorias/${encodeURIComponent(id)}/${accion}`

/** El gerente recibe también las archivadas; una asistente, solo las activas. */
export const listarCategorias = () => solicitar<Categoria[]>('/categorias?archivadas=true')

export const crearCategoria = (datos: DatosCategoria) => enviarJson<Categoria>('/categorias', datos)

export const editarCategoria = (id: string, datos: DatosCategoria) =>
  enviarJson<Categoria>(ruta(id, 'edicion'), datos)

export const archivarCategoria = (id: string, motivo: string | null) =>
  enviarJson<Categoria>(ruta(id, 'archivado'), { motivo })

export const reactivarCategoria = (id: string) =>
  enviarJson<Categoria>(ruta(id, 'reactivacion'), {})
