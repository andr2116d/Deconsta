import type { EstadoPago } from '@/features/deudas/types'
import type { EstadoMora } from '@/features/pagos/types'
import type { NombreIcono } from '@/shared/components/iconos'

import type { AccionHistorial, EstadoFiltro } from './types'

export const ESTADOS_FILTRO: readonly { valor: EstadoFiltro; etiqueta: string; grupo: string }[] = [
  { valor: 'por_autorizar', etiqueta: 'Espera autorización', grupo: 'Deuda' },
  { valor: 'registrada', etiqueta: 'Registrada', grupo: 'Deuda' },
  { valor: 'rechazada', etiqueta: 'Rechazada', grupo: 'Deuda' },
  { valor: 'anulada', etiqueta: 'Anulada', grupo: 'Deuda' },
  { valor: 'por_verificar', etiqueta: 'Pago por verificar', grupo: 'Pago' },
  { valor: 'confirmado', etiqueta: 'Pago confirmado', grupo: 'Pago' },
  { valor: 'devuelto', etiqueta: 'Pago devuelto', grupo: 'Pago' },
  { valor: 'mora', etiqueta: 'Con mora', grupo: 'Pago' },
]

export const esEstadoFiltro = (valor: unknown): valor is EstadoFiltro =>
  ESTADOS_FILTRO.some((e) => e.valor === valor)

export const PAGOS: Record<EstadoPago, { texto: string; clase: string }> = {
  confirmado: { texto: 'Pagada', clase: 'bg-exito-fondo text-exito' },
  por_verificar: { texto: 'Pago por verificar', clase: 'bg-rosa text-ciruela' },
  devuelto: { texto: 'Pago devuelto', clase: 'bg-error-fondo text-error' },
}

export const MORAS: Record<EstadoMora, { texto: string; clase: string }> = {
  por_aprobar: { texto: 'Mora por aprobar', clase: 'bg-aviso-fondo text-aviso' },
  aprobada: { texto: 'Mora aprobada', clase: 'bg-exito-fondo text-exito' },
  rechazada: { texto: 'Mora rechazada', clase: 'bg-fondo text-secundario' },
}

/** Cómo se cuenta cada paso en la línea de tiempo: «Lucía registró la deuda». */
export const ACCIONES: Record<AccionHistorial, { texto: string; icono: NombreIcono }> = {
  DEUDA_REGISTRADA: { texto: 'registró la deuda', icono: 'documento' },
  DEUDA_AUTORIZADA: { texto: 'autorizó la deuda', icono: 'escudo' },
  DEUDA_RECHAZADA: { texto: 'rechazó la deuda', icono: 'cerrar' },
  DEUDA_REVISADA: { texto: 'dio su visto bueno', icono: 'check' },
  DEUDA_ANULADA: { texto: 'anuló la deuda', icono: 'cerrar' },
  PAGO_REGISTRADO: { texto: 'registró el pago', icono: 'archivo' },
  PAGO_CONFIRMADO: { texto: 'confirmó el pago', icono: 'check' },
  PAGO_DEVUELTO: { texto: 'devolvió el pago', icono: 'cerrar' },
  MORA_DECLARADA: { texto: 'declaró una mora', icono: 'alerta' },
  MORA_APROBADA: { texto: 'aprobó la mora', icono: 'check' },
  MORA_RECHAZADA: { texto: 'rechazó la mora', icono: 'cerrar' },
  PAGO_PEDIDO: { texto: 'pidió que la paguen', icono: 'reloj' },
  PEDIDO_RETIRADO: { texto: 'retiró el pedido de pago', icono: 'cerrar' },
}

const fechaHora = new Intl.DateTimeFormat('es-PE', {
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'America/Lima',
})

/** «21 oct, 3:40 p. m.», en la hora del espacio. */
export const formatearMomento = (iso: string) => fechaHora.format(new Date(iso))
