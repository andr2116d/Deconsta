import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ErrorApi } from '@/shared/api/http'

import * as api from '../api/acceso'
import type { CambioContrasena, Credenciales, Ingreso, Sesion } from '../types'

/**
 * Estado de la sesión en el navegador. El token vive en una cookie HttpOnly que el JavaScript no
 * puede leer: aquí solo se guarda lo que la API devuelve para pintar la interfaz. El backend
 * vuelve a comprobar la sesión en cada solicitud.
 */
export const useSesionStore = defineStore('sesion', () => {
  const sesion = ref<Sesion | null>(null)
  const comprobada = ref(false)

  const usuario = computed(() => sesion.value?.usuario ?? null)
  const autenticada = computed(() => sesion.value !== null)
  const debeCambiarContrasena = computed(() => sesion.value?.debe_cambiar_contrasena ?? false)
  const pasosPendientes = computed(() => sesion.value?.pasos_pendientes ?? [])
  const pasoActual = computed(() => pasosPendientes.value[0] ?? null)

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
  }

  return {
    sesion,
    usuario,
    autenticada,
    debeCambiarContrasena,
    pasosPendientes,
    pasoActual,
    comprobar,
    recargar,
    actualizar,
    ingresar,
    cambiarContrasena,
    salir,
    olvidar,
  }
})
