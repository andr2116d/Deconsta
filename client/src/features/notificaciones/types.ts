export type TipoNotificacion =
  | 'DEUDA_POR_AUTORIZAR'
  | 'DEUDA_REGISTRADA'
  | 'REGISTRO_BLOQUEADO'
  | 'PAGO_POR_VERIFICAR'
  | 'REGISTRO_PAGOS_BLOQUEADO'
  | 'MORA_POR_APROBAR'
  | 'DEUDA_AUTORIZADA'
  | 'DEUDA_RECHAZADA'
  | 'DEUDA_ANULADA'
  | 'REGISTRO_DESBLOQUEADO'
  | 'REGISTRO_PAGOS_DESBLOQUEADO'
  | 'PAGO_CONFIRMADO'
  | 'PAGO_DEVUELTO'
  | 'MORA_APROBADA'
  | 'MORA_RECHAZADA'

export interface Notificacion {
  id: string
  tipo: TipoNotificacion
  titulo: string
  cuerpo: string
  deuda_id: string | null
  /** Cuenta a la que se refiere (la asistente bloqueada, por ejemplo). */
  cuenta_id: string | null
  creada_en: string
  leida: boolean
}

export interface Bandeja {
  notificaciones: Notificacion[]
  no_leidas: number
}
