import type { TipoDocumento } from '@/shared/validaciones/persona'

/** pendiente: aún no completa su primer ingreso (confirmar sus datos). */
export type EstadoAsistente = 'activa' | 'bloqueada' | 'pendiente'

export interface Asistente {
  id: string
  nombre_usuario: string
  nombres: string
  apellidos: string
  cargo: string | null
  telefono: string | null
  /** Lo completa la asistente en su primer ingreso. */
  correo: string | null
  tipo_documento: TipoDocumento
  /** Enmascarado: solo los últimos dígitos. */
  documento: string
  estado: EstadoAsistente
  causa_bloqueo: 'intentos_fallidos' | 'gerente' | null
  bloqueada: boolean
  debe_cambiar_contrasena: boolean
  ultimo_ingreso_en: string | null
}

/** Se muestran una sola vez: Deconsta no vuelve a conocer la contraseña. */
export interface Credenciales {
  asistente: Asistente
  nombre_usuario: string
  contrasena_temporal: string
}

export interface NuevaAsistente {
  nombres: string
  apellidos: string
  telefono: string
  tipo_documento: TipoDocumento
  numero_documento: string
  cargo: string | null
  /** null: Deconsta lo genera. */
  nombre_usuario: string | null
  contrasena: string | null
  crear_aunque_eliminada?: boolean
}

/** La persona fue eliminada antes de este equipo: se puede recuperar. */
export interface CuentaEliminada {
  id: string
  nombre_usuario: string
}
