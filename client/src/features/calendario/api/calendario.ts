import { solicitar } from '@/shared/api/http'

import type { Calendario, Dia } from '../types'

/** Las cuotas que vencen entre dos días (como máximo 62). El backend decide qué ve cada cuenta. */
export const consultarCalendario = (desde: Dia, hasta: Dia) =>
  solicitar<Calendario>(`/deudas/calendario?${new URLSearchParams({ desde, hasta })}`)
