import { descargar, solicitar } from '@/shared/api/http'

import type { FiltrosHistorial, Historial } from '../types'

function parametros(filtros: FiltrosHistorial, extra: Record<string, string> = {}) {
  const datos = new URLSearchParams()
  for (const [clave, valor] of Object.entries({ ...filtros, ...extra })) {
    if (valor) datos.set(clave, valor)
  }
  const texto = datos.toString()
  return texto ? `?${texto}` : ''
}

/** Una página del historial. `mios` es «Mis registros»: lo que la cuenta registró o pagó. */
export const consultarHistorial = (
  filtros: FiltrosHistorial,
  { cursor, mios }: { cursor?: string; mios?: boolean } = {},
) =>
  solicitar<Historial>(
    `/historial${parametros(filtros, { ...(cursor ? { cursor } : {}), ...(mios ? { mios: 'true' } : {}) })}`,
  )

/** El CSV con una fila por cuota. Solo para el gerente. */
export const exportarHistorial = (filtros: FiltrosHistorial) =>
  descargar(`/historial/exportacion${parametros(filtros)}`)
