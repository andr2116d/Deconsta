import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ErrorApi } from '@/shared/api/http'

import * as api from '../api/acceso'
import type { CambioContrasena, Credenciales, Ingreso, Sesion } from '../types'

// Quien cierra el recordatorio de la contraseña temporal no lo vuelve a ver al recargar la página,
// pero sí en su siguiente ingreso. Se guarda por pestaña; si el navegador no deja guardarlo, el
// recordatorio solo vuelve a aparecer antes de lo previsto.
const CLAVE_POSPUESTA = 'deconsta:contrasena-pospuesta'

function leerPospuesta(): string | null {
  try {
    return sessionStorage.getItem(CLAVE_POSPUESTA)
  } catch {
    return null
  }
}

function guardarPospuesta(usuarioId: string | null): void {
  try {
    if (usuarioId) sessionStorage.setItem(CLAVE_POSPUESTA, usuarioId)
    else sessionStorage.removeItem(CLAVE_POSPUESTA)
  } catch {
    // Sin almacenamiento disponible: el recordatorio dura lo que dure la página abierta.
  }
}

/**
 * Estado de la sesión en el navegador. El token vive en una cookie HttpOnly que el JavaScript no
 * puede leer: aquí solo se guarda lo que la API devuelve para pintar la interfaz. El backend
 * vuelve a comprobar la sesión en cada solicitud.
 */
export const useSesionStore = defineStore('sesion', () => {
  const sesion = ref<Sesion | null>(null)
  const comprobada = ref(false)
  const pospuestaPor = ref<string | null>(leerPospuesta())

  const usuario = computed(() => sesion.value?.usuario ?? null)
  const autenticada = computed(() => sesion.value !== null)
  const debeCambiarContrasena = computed(() => sesion.value?.debe_cambiar_contrasena ?? false)
  const pasosPendientes = computed(() => sesion.value?.pasos_pendientes ?? [])
  const pasoActual = computed(() => pasosPendientes.value[0] ?? null)
  /** El backend sigue marcando la contraseña como temporal y la cuenta no pospuso el aviso. */
  const recordarContrasena = computed(
    () => debeCambiarContrasena.value && pospuestaPor.value !== usuario.value?.id,
  )

  function posponerCambioContrasena(): void {
    pospuestaPor.value = usuario.value?.id ?? null
    guardarPospuesta(pospuestaPor.value)
  }

  function olvidarPospuesta(): void {
    pospuestaPor.value = null
    guardarPospuesta(null)
  }

  async function comprobar(): Promise<void> {
    if (comprobada.value) return
    try {
      sesion.value = await api.obtenerSesion()
    } catch (error) {
      if (!(error instanceof ErrorApi) || error.estado !== 401) throw error
      sesion.value = null
    }
    comprobada.value = true
  }

  async function ingresar(credenciales: Credenciales): Promise<Ingreso> {
    const ingreso = await api.iniciarSesion(credenciales)
    sesion.value = ingreso
    comprobada.value = true
    // Cada ingreso vuelve a recordar la contraseña temporal.
    olvidarPospuesta()
    return ingreso
  }

  async function cambiarContrasena(datos: CambioContrasena): Promise<void> {
    sesion.value = await api.cambiarContrasena(datos)
  }

  /** Vuelve a pedir la sesión: los pasos pendientes pueden haber cambiado en el backend. */
  async function recargar(): Promise<void> {
    comprobada.value = false
    await comprobar()
  }

  function actualizar(nueva: Sesion): void {
    sesion.value = nueva
  }

  async function salir(): Promise<void> {
    try {
      await api.cerrarSesion()
    } finally {
      olvidar()
    }
  }

  function olvidar(): void {
    sesion.value = null
    comprobada.value = true
    olvidarPospuesta()
  }

  return {
    sesion,
    usuario,
    autenticada,
    debeCambiarContrasena,
    pasosPendientes,
    pasoActual,
    recordarContrasena,
    posponerCambioContrasena,
    comprobar,
    recargar,
    actualizar,
    ingresar,
    cambiarContrasena,
    salir,
    olvidar,
  }
})
