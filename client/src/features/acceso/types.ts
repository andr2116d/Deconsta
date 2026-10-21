export type Rol = 'gerente' | 'asistente'

export interface Usuario {
  id: string
  nombre_usuario: string
  nombres: string
  rol: Rol
}

export interface Sesion {
  usuario: Usuario
  debe_cambiar_contrasena: boolean
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
