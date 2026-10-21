export type Rol = 'gerente' | 'asistente'

export interface Usuario {
  id: string
  nombre_usuario: string
  nombres: string
  rol: Rol
}

/** Pasos del primer ingreso, en el orden en que deben completarse. */
export type PasoPendiente = 'cambiar_contrasena' | 'aceptar_documentos'

export interface Sesion {
  usuario: Usuario
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
