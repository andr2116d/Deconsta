import type { Rol } from '@/features/acceso/types'

export type TipoDocumento = 'dni' | 'ce'

export interface CambiosNombreUsuario {
  maximo: number
  usados: number
  restantes: number
  /** Inicio del mes siguiente (hora de Lima): desde entonces vuelve a haber cupo. */
  renueva_en: string
}

/** Datos de la propia cuenta, tal como los devuelve la API. */
export interface Cuenta {
  id: string
  rol: Rol
  nombre_usuario: string
  nombres: string
  apellidos: string
  correo: string
  telefono: string | null
  tipo_documento: TipoDocumento
  numero_documento: string
  /** Solo del gerente; en una asistente siempre es null. */
  nombre_recibos: string | null
  /** Lo fija quien crea la cuenta; la persona no lo edita. */
  cargo: string | null
  debe_cambiar_contrasena: boolean
  contrasena_actualizada_en: string
  cambios_nombre_usuario: CambiosNombreUsuario
}

/** Lo que la persona puede editar en «Mis datos». */
export interface DatosEditables {
  nombres: string
  apellidos: string
  correo: string
  telefono: string | null
  tipo_documento: TipoDocumento
  numero_documento: string
  nombre_recibos: string | null
}

export interface ActualizacionDatos extends DatosEditables {
  contrasena_actual?: string
  confirmar_cambio_documento?: boolean
}

export interface CambioNombreUsuario {
  nombre_usuario: string
  contrasena_actual: string
}
