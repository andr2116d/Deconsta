import { enviarJson, solicitar } from '@/shared/api/http'

import type { ActualizacionDatos, CambioNombreUsuario, Cuenta } from '../types'

export const obtenerCuenta = () => solicitar<Cuenta>('/cuenta')

export const actualizarDatos = (datos: ActualizacionDatos) =>
  enviarJson<Cuenta>('/cuenta/datos', datos)

export const cambiarNombreUsuario = (datos: CambioNombreUsuario) =>
  enviarJson<Cuenta>('/cuenta/nombre-usuario', datos)
