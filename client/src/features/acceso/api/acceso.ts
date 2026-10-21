import { enviarJson, solicitar } from '@/shared/api/http'

import type { CambioContrasena, Credenciales, Ingreso, Sesion } from '../types'

export const iniciarSesion = (credenciales: Credenciales) =>
  enviarJson<Ingreso>('/auth/login', credenciales)

export const obtenerSesion = () => solicitar<Sesion>('/auth/me')

export const cerrarSesion = () => enviarJson<void>('/auth/logout')

export const cambiarContrasena = (datos: CambioContrasena) =>
  enviarJson<Sesion>('/auth/contrasena', datos)
