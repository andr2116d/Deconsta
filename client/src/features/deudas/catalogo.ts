import type { NombreIcono } from '@/shared/components/iconos'

import type { EstadoDeuda, LugarPago, MotivoEspera, TipoDocumento } from './types'

/** Dónde se paga una deuda. El backend acepta solo estos valores. */
export const LUGARES_PAGO: readonly {
  valor: LugarPago
  etiqueta: string
  detalle: string
  icono: NombreIcono
}[] = [
  {
    valor: 'agente',
    etiqueta: 'Agente o agencia',
    detalle: 'BCP, BBVA, Interbank…',
    icono: 'banco',
  },
  {
    valor: 'banca_digital',
    etiqueta: 'Banca por internet',
    detalle: 'Pago de servicios en la web o app',
    icono: 'internet',
  },
  {
    valor: 'billetera',
    etiqueta: 'Billetera digital',
    detalle: 'Yape, Plin',
    icono: 'telefono',
  },
  {
    valor: 'transferencia',
    etiqueta: 'Transferencia',
    detalle: 'A la cuenta del emisor',
    icono: 'tarjeta',
  },
  {
    valor: 'ventanilla',
    etiqueta: 'Ventanilla del emisor',
    detalle: 'En sus oficinas',
    icono: 'vivienda',
  },
  {
    valor: 'debito_automatico',
    etiqueta: 'Débito automático',
    detalle: 'Se carga solo a una cuenta',
    icono: 'reloj',
  },
]

export const TIPOS_DOCUMENTO: Record<TipoDocumento, string> = {
  recibo_servicio: 'Recibo de servicio',
  boleta: 'Boleta',
  factura: 'Factura',
  cronograma: 'Cronograma de pagos',
  papeleta: 'Papeleta',
  tributo: 'Tributo',
  otro: 'Documento',
}

export const MOTIVOS: Record<MotivoEspera, string> = {
  IMPORTE_SOBRE_LIMITE: 'Supera tu límite',
  TITULAR_DISTINTO: 'Otro titular',
  DOCUMENTO_DUDOSO: 'Documento por revisar',
  DATOS_CORREGIDOS: 'Datos corregidos a mano',
}

export const CAMPOS_CORREGIDOS: Record<string, string> = {
  importe: 'Importe',
  vencimiento: 'Vencimiento',
  codigo_pago: 'Código de pago',
  titular: 'Titular',
}

export const ESTADOS: Record<EstadoDeuda, { texto: string; clase: string }> = {
  por_autorizar: { texto: 'Espera autorización', clase: 'bg-aviso-fondo text-aviso' },
  registrada: { texto: 'Registrada', clase: 'bg-exito-fondo text-exito' },
  rechazada: { texto: 'Rechazada', clase: 'bg-error-fondo text-error' },
  anulada: { texto: 'Anulada', clase: 'bg-fondo text-secundario' },
}

const fecha = new Intl.DateTimeFormat('es-PE', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

/** «28 oct 2026». Las fechas de la deuda son días, sin hora: se leen en UTC. */
export const formatearFecha = (dia: string) => fecha.format(new Date(`${dia}T00:00:00Z`))
