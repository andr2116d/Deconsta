import { defineStore } from 'pinia'
import { ref } from 'vue'

import { useSesionStore } from '@/features/acceso/stores/sesion'

import * as api from '../api/cuenta'
import type { ActualizacionDatos, CambioNombreUsuario, Cuenta } from '../types'

/**
 * Datos de «Mi cuenta». Los comparten las pestañas y la tarjeta lateral: al guardar, todo lo que
 * los muestra (incluida la cabecera) se actualiza sin recargar.
 */
export const useCuentaStore = defineStore('cuenta', () => {
  const sesion = useSesionStore()
  const cuenta = ref<Cuenta | null>(null)
  const cargando = ref(false)
  const errorCarga = ref<unknown>(null)

  function aplicar(nueva: Cuenta): Cuenta {
    cuenta.value = nueva
    sesion.actualizarUsuario({ nombres: nueva.nombres, nombre_usuario: nueva.nombre_usuario })
    return nueva
  }

  /** Siempre consulta la API: los datos pudieron cambiar desde otra sesión. */
  async function cargar(): Promise<void> {
    // Nunca se muestran, ni por un instante, los datos de otra cuenta.
    if (cuenta.value && cuenta.value.id !== sesion.usuario?.id) cuenta.value = null
    cargando.value = true
    errorCarga.value = null
    try {
      aplicar(await api.obtenerCuenta())
    } catch (error) {
      errorCarga.value = error
      throw error
    } finally {
      cargando.value = false
    }
  }

  const guardarDatos = async (datos: ActualizacionDatos) =>
    aplicar(await api.actualizarDatos(datos))

  const cambiarNombreUsuario = async (datos: CambioNombreUsuario) =>
    aplicar(await api.cambiarNombreUsuario(datos))

  return { cuenta, cargando, errorCarga, cargar, guardarDatos, cambiarNombreUsuario }
})
