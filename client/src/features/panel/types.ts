import type { Rol } from '@/features/acceso/types'
import type { LugarPago } from '@/features/deudas/types'

export type TipoPendiente = 'autorizar_deuda' | 'revisar_deuda' | 'verificar_pago' | 'aprobar_mora'

/** Lo que espera la decisión del gerente. */
export interface Pendiente {
  tipo: TipoPendiente
  /** El id de la deuda, del pago o de la mora, según el tipo. */
  id: string
  deuda_id: string
  concepto: string
  importe: string
  vence_el: string
  /** Quién lo dejó para el gerente. */
  por: string
  desde: string
}

export interface CuotaPanel {
  deuda_id: string
  concepto: string
  categoria_id: string | null
  cuota: number
  cuotas: number
  importe: string
  vence_el: string
  lugares_pago: LugarPago[]
  pedido: { id: string; asistente_id: string; asistente: string; nota: string | null } | null
}

export interface Resumen {
  por_pagar: string
  cuotas_por_pagar: number
  vencidas: number
  pagado_mes: string
  pagos_mes: number
  pendientes: Pendiente[]
  proximas: CuotaPanel[]
}

export interface Jornada {
  por_completar: number
  /** Cuotas por pagar cuyo último pago devolvió el gerente. */
  devueltas: number
  en_manos_del_gerente: number
  gerente: string
  /** Primero lo que pidió el gerente; si no hay, lo que vence antes. */
  siguiente: CuotaPanel | null
  /** Sobre este importe, lo registrado espera autorización; null: sin límite. */
  limite: string | null
}

export interface Panel {
  hoy: string
  rol: Rol
  resumen: Resumen | null
  jornada: Jornada | null
}
