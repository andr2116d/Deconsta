import type { EstadoPago, LugarPago, Riesgo, Senal, TipoDocumento } from '@/features/deudas/types'

export type { EstadoPago }

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
  lugar_pago: LugarPago | null
  pagado_el: string
  estado: EstadoPago
  /** De 0 a 95: cuánto respaldan los comprobantes que el pago es verdadero. */
  confianza: number
  comprobaciones: Comprobacion[]
  comprobantes: string[]
  registrado_por: string
  registrado_en: string
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
