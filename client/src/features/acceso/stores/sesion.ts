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
    comprobar,
    ingresar,
    cambiarContrasena,
    salir,
    olvidar,
  }
})
