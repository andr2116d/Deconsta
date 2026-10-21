import { solicitar } from '@/shared/api/http'

import type { Panel } from '../types'

/** El resumen del gerente o la jornada de la asistente, según la sesión. */
export const consultarPanel = () => solicitar<Panel>('/panel')
