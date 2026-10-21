import type { EstadoDeuda, EstadoPago, LugarPago, TipoDocumento } from '@/features/deudas/types'

/** Día sin hora, «AAAA-MM-DD». */
export type Dia = string

/** Mes, «AAAA-MM». */
export type Mes = string

/** Una cuota que vence en el rango pedido, con la deuda a la que pertenece. */
export interface Vencimiento {
  deuda_id: string
  concepto: string
  categoria_id: string | null
  tipo_documento: TipoDocumento
  lugares_pago: LugarPago[]
  /** El pago vigente de esta cuota; null si falta pagarla. */
  pago: EstadoPago | null
  estado: EstadoDeuda
  revision_pendiente: boolean
  vence_el: Dia
  /** En soles: el importe de esta cuota, no el de toda la deuda. */
  importe: string
  cuota: number
  /** Cuántas cuotas tiene la deuda: 1 en un recibo. */
  cuotas: number
  registrada_por: string
}

export interface Calendario {
  /** El día de hoy según el backend, en la zona del espacio. */
  hoy: Dia
  desde: Dia
  hasta: Dia
  vencimientos: Vencimiento[]
}
