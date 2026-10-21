import type {
  EstadoDeuda,
  EstadoPago,
  LugarPago,
  MotivoEspera,
  TipoDocumento,
} from '@/features/deudas/types'
import type { EstadoMora } from '@/features/pagos/types'

/** El estado de la deuda, el de alguno de sus pagos o que tenga una mora. */
export type EstadoFiltro = EstadoDeuda | EstadoPago | 'mora'

export interface FiltrosHistorial {
  desde?: string
  hasta?: string
  estado?: EstadoFiltro
  categoria_id?: string
  registrada_por?: string
  pagado_por?: string
  lugar_pago?: LugarPago
  /** Busca en el concepto. */
  q?: string
}

export type AccionHistorial =
  | 'DEUDA_REGISTRADA'
  | 'DEUDA_AUTORIZADA'
  | 'DEUDA_RECHAZADA'
  | 'DEUDA_REVISADA'
  | 'DEUDA_ANULADA'
  | 'PAGO_REGISTRADO'
  | 'PAGO_CONFIRMADO'
  | 'PAGO_DEVUELTO'
  | 'MORA_DECLARADA'
  | 'MORA_APROBADA'
  | 'MORA_RECHAZADA'
  | 'PAGO_PEDIDO'
  | 'PEDIDO_RETIRADO'

export interface EventoHistorial {
  accion: AccionHistorial
  en: string
  /** Quién lo hizo; null si la cuenta ya no existe. */
  actor: string | null
  motivo: string | null
  cuota: number | null
}

export interface PagoHistorial {
  id: string
  cuota: number
  importe: string
  comision: string
  mora: string
  lugar_pago: LugarPago | null
  pagado_el: string
  estado: EstadoPago
  /** Solo para el gerente. */
  confianza: number | null
  registrado_por: string
  registrado_en: string
  decidido_en: string | null
  motivo_decision: string | null
}

export interface MoraHistorial {
  id: string
  cuota: number
  importe: string
  estado: EstadoMora
  declarada_por: string
  declarada_en: string
  decidida_en: string | null
  motivo_decision: string | null
}

export interface CuotaHistorial {
  numero: number
  vence_el: string
  importe: string
  /** El pago vigente; null si falta pagarla. */
  pago: EstadoPago | null
  /** La mora que no fue rechazada. */
  mora: EstadoMora | null
}

export interface DeudaHistorial {
  id: string
  concepto: string
  categoria_id: string | null
  tipo_documento: TipoDocumento
  lugares_pago: LugarPago[]
  importe: string
  estado: EstadoDeuda
  revision_pendiente: boolean
  motivos: MotivoEspera[]
  registrada_por: string
  registrada_por_id: string
  creado_en: string
  motivo_decision: string | null
  cuotas: CuotaHistorial[]
  pagos: PagoHistorial[]
  moras: MoraHistorial[]
  eventos: EventoHistorial[]
}

export interface Historial {
  hoy: string
  /** El rango aplicado: sin fechas, los últimos 90 días. */
  desde: string
  hasta: string
  deudas: DeudaHistorial[]
  /** Para pedir la página siguiente; null si no hay más. */
  siguiente: string | null
}
