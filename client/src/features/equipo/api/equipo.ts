import { enviarJson, solicitar } from '@/shared/api/http'

import type { Asistente, Credenciales, NuevaAsistente } from '../types'

const ruta = (id: string, accion: string) => `/asistentes/${encodeURIComponent(id)}/${accion}`

export const listarAsistentes = () => solicitar<Asistente[]>('/asistentes')

export const registrarAsistente = (datos: NuevaAsistente) =>
  enviarJson<Credenciales>('/asistentes', datos)

export const bloquearAsistente = (id: string, motivo: string | null) =>
  enviarJson<Asistente>(ruta(id, 'bloqueo'), { motivo })

export const desbloquearAsistente = (id: string) =>
  enviarJson<Asistente>(ruta(id, 'desbloqueo'), {})

export const eliminarAsistente = (id: string, motivo: string | null) =>
  enviarJson<void>(ruta(id, 'eliminacion'), { motivo })

export const recuperarAsistente = (id: string) =>
  enviarJson<Credenciales>(ruta(id, 'recuperacion'), {})

export const restablecerContrasena = (id: string, motivo: string | null) =>
  enviarJson<Credenciales>(ruta(id, 'restablecimiento'), { motivo })
