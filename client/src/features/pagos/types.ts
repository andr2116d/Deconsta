import type { EstadoPago, LugarPago, Riesgo, Senal, TipoDocumento } from '@/features/deudas/types'

export type { EstadoPago }

/** Para qué se subió el archivo: el voucher de un pago o la prueba de una mora. */
export type Proposito = 'pago' | 'mora'

export type EstadoMora = 'por_aprobar' | 'aprobada' | 'rechazada'

export type EstadoComprobante =
  'analizando' | 'listo' | 'ilegible' | 'rechazado' | 'repetido' | 'fallido'

/** Lo que se leyó del comprobante, para que quien lo subió lo reconozca. */
export interface Lectura {
  lugar: LugarPago | null
  medio: string | null
  empresa: string | null
  numero_operacion: string | null
  pagado_el: string | null
  /** En soles, como texto: lo pagado por el servicio. */
  importe: string | null
  comision: string | null
  /** En la prueba de una mora: la mora, si figura aparte. */
  mora: string | null
}

export interface Comprobante {
  id: string
  deuda_id: string
  cuota: number
  estado: EstadoComprobante
  tipo_archivo: string
  nombre_archivo: string
  tamano: number
  subido_en: string
  analizado_en: string | null
  riesgo: Riesgo | null
  senales: Senal[]
  lectura: Lectura | null
  pago_id: string | null
  proposito: Proposito
  /** Quien lo subió tiene el registro de pagos en pausa. */
  registro_bloqueado: boolean
}

export interface CuotaPorPagar {
  deuda_id: string
  concepto: string
  categoria_id: string | null
  tipo_documento: TipoDocumento
  lugares_pago: LugarPago[]
  codigo_pago: string | null
  cuota: number
  cuotas: number
  vence_el: string
  /** En soles: el importe de esta cuota. */
  importe: string
  vencida_hace: number | null
  registrada_por: string
  /** Por qué el gerente devolvió el último pago de esta cuota, si lo devolvió. */
  devuelto_por: string | null
  /** La mora vigente de la cuota o, si no hay, la última rechazada. */
  mora: MoraResumen | null
  /** El pedido pendiente del gerente para pagarla. */
  pedido: PedidoResumen | null
}

export interface PedidoResumen {
  id: string
  asistente_id: string
  asistente: string
  nota: string | null
  pedido_en: string
}

export interface MoraResumen {
  id: string
  estado: EstadoMora
  /** En soles: la mora, sin la cuota. */
  importe: string
  motivo_decision: string | null
}

export interface Mora {
  id: string
  deuda_id: string
  concepto: string
  cuota: number
  importe: string
  importe_cuota: string
  nota: string | null
  estado: EstadoMora
  /** Solo para el gerente, como en los pagos. */
  confianza: number | null
  comprobaciones: Comprobacion[] | null
  prueba_id: string
  declarada_por: string
  declarada_en: string
  decidida_en: string | null
  motivo_decision: string | null
}

export interface MoraDetalle extends Mora {
  prueba: Comprobante | null
}

export interface NuevaMora {
  deuda_id: string
  cuota: number
  /** En soles, como texto («14.40»). */
  importe: string
  prueba_id: string
  nota: string | null
}

export interface PorPagar {
  /** El día de hoy en la zona del espacio, según el backend. */
  hoy: string
  cuotas: CuotaPorPagar[]
  registro_bloqueado: boolean
}

export type ResultadoComprobacion = 'bien' | 'sin_dato' | 'aviso'

export interface Comprobacion {
  codigo: string
  titulo: string
  resultado: ResultadoComprobacion
  detalle: string
}

export interface Pago {
  id: string
  deuda_id: string
  concepto: string
  cuota: number
  importe: string
  comision: string
  /** Lo pagado por una mora aprobada, dentro del importe. */
  mora: string
  lugar_pago: LugarPago | null
  pagado_el: string
  estado: EstadoPago
  /** Solo para el gerente: de 0 a 95, cuánto respaldan los comprobantes que el pago es verdadero. */
  confianza: number | null
  comprobaciones: Comprobacion[] | null
  comprobantes: string[]
  registrado_por: string
  registrado_en: string
  decidido_en: string | null
  motivo_decision: string | null
}

export interface PagoDetalle extends Pago {
  cuotas: number
  detalle_comprobantes: Comprobante[]
}

export interface NuevoPago {
  deuda_id: string
  cuota: number
  comprobantes: string[]
}

export interface BloqueoPagos {
  asistente_id: string
  bloqueado_en: string
}

/** El gerente pidió a una asistente pagar una cuota; sigue pendiente mientras falte pagarla. */
export interface Pedido extends PedidoResumen {
  deuda_id: string
  concepto: string
  cuota: number
  cuotas: number
  /** En soles: el importe de la cuota. */
  importe: string
  vence_el: string
  vencida_hace: number | null
}

export interface NuevoPedido {
  deuda_id: string
  cuota: number
  asistente_id: string
  nota: string | null
}
