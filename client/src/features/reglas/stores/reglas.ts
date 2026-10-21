import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '../api/reglas'
import type { EdicionTitular, NuevoTitular, Reglas, Titular } from '../types'

const porNombre = (a: Titular, b: Titular) =>
  a.nombre.localeCompare(b.nombre, 'es', { sensitivity: 'base' })

/**
 * Reglas de autorización del espacio. Cada operación actualiza el estado con lo que devuelve la
 * API, así la pantalla cambia al momento sin volver a cargar todo.
 */
export const useReglasStore = defineStore('reglas', () => {
  const reglas = ref<Reglas | null>(null)
  const cargando = ref(false)
  const errorCarga = ref<unknown>(null)

  async function cargar(): Promise<void> {
    cargando.value = true
    errorCarga.value = null
    try {
      reglas.value = await api.consultarReglas()
    } catch (error) {
      errorCarga.value = error
      throw error
    } finally {
      cargando.value = false
    }
  }

  function conTitulares(titulares: Titular[]) {
    if (reglas.value) reglas.value = { ...reglas.value, titulares: [...titulares].sort(porNombre) }
  }

  async function cambiarLimite(limite: string | null): Promise<Reglas> {
    reglas.value = await api.cambiarLimite(limite)
    return reglas.value
  }

  async function agregarTitular(nuevo: NuevoTitular): Promise<Titular> {
    const titular = await api.agregarTitular(nuevo)
    conTitulares([...(reglas.value?.titulares ?? []), titular])
    return titular
  }

  async function editarTitular(id: string, datos: EdicionTitular): Promise<Titular> {
    const titular = await api.editarTitular(id, datos)
    conTitulares((reglas.value?.titulares ?? []).map((t) => (t.id === id ? titular : t)))
    return titular
  }

  async function quitarTitular(id: string, motivo: string | null): Promise<void> {
    await api.quitarTitular(id, motivo)
    conTitulares((reglas.value?.titulares ?? []).filter((t) => t.id !== id))
  }

  /** Al cambiar de cuenta no quedan datos de otro espacio en memoria. */
  function olvidar(): void {
    reglas.value = null
  }

  return {
    reglas,
    cargando,
    errorCarga,
    cargar,
    cambiarLimite,
    agregarTitular,
    editarTitular,
    quitarTitular,
    olvidar,
  }
})
