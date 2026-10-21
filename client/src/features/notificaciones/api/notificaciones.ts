import { enviarJson, solicitar } from '@/shared/api/http'

import type { Bandeja } from '../types'

export const RUTA_FLUJO = '/api/v1/notificaciones/flujo'

export const listarNotificaciones = () => solicitar<Bandeja>('/notificaciones')

export const marcarLeida = (id: string) =>
  enviarJson<void>(`/notificaciones/${encodeURIComponent(id)}/lectura`)

export const marcarTodasLeidas = () => enviarJson<{ marcadas: number }>('/notificaciones/lectura')
