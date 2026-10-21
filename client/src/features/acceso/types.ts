export type Rol = 'gerente' | 'asistente'

export interface Usuario {
  id: string
  nombre_usuario: string
  nombres: string
  rol: Rol
}

/**
 * Pasos obligatorios del primer ingreso, en orden. «completar_datos» solo lo tiene una asistente
 * registrada (o recuperada) desde Mi equipo. La contraseña temporal no es un paso: se recuerda.
 */
export type PasoPendiente = 'aceptar_documentos' | 'completar_datos'

export interface Sesion {
  usuario: Usuario
  /** La cuenta sigue con la contraseña temporal: se recuerda en cada ingreso hasta cambiarla. */
  debe_cambiar_contrasena: boolean
  pasos_pendientes: PasoPendiente[]
}

export interface Ingreso extends Sesion {
  primer_ingreso: boolean
}

export interface Credenciales {
  nombre_usuario: string
  contrasena: string
}

export interface CambioContrasena {
  contrasena_actual: string
  contrasena_nueva: string
}
