import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '../api/equipo'
import type { Asistente, Credenciales, NuevaAsistente } from '../types'

/**
 * Asistentes del equipo del gerente. Cada operación actualiza la lista con lo que devuelve la API,
 * así la pantalla cambia al momento sin volver a cargar todo.
 */
export const useEquipoStore = defineStore('equipo', () => {
  const asistentes = ref<Asistente[] | null>(null)
  const cargando = ref(false)
  const errorCarga = ref<unknown>(null)

  function reemplazar(asistente: Asistente): Asistente {
    const lista = asistentes.value ?? []
    const indice = lista.findIndex((a) => a.id === asistente.id)
    asistentes.value =
      indice === -1
        ? [...lista, asistente]
        : lista.map((a) => (a.id === asistente.id ? asistente : a))
    return asistente
  }

  async function cargar(): Promise<void> {
    cargando.value = true
    errorCarga.value = null
    try {
      asistentes.value = await api.listarAsistentes()
    } catch (error) {
      errorCarga.value = error
      throw error
    } finally {
      cargando.value = false
    }
  }

  async function registrar(nueva: NuevaAsistente): Promise<Credenciales> {
    const credenciales = await api.registrarAsistente(nueva)
    reemplazar(credenciales.asistente)
    return credenciales
  }

  async function recuperar(id: string): Promise<Credenciales> {
    const credenciales = await api.recuperarAsistente(id)
    reemplazar(credenciales.asistente)
    return credenciales
  }

  async function restablecer(id: string, motivo: string | null): Promise<Credenciales> {
    const credenciales = await api.restablecerContrasena(id, motivo)
    reemplazar(credenciales.asistente)
    return credenciales
  }

  const bloquear = async (id: string, motivo: string | null) =>
    reemplazar(await api.bloquearAsistente(id, motivo))

  const desbloquear = async (id: string) => reemplazar(await api.desbloquearAsistente(id))

  async function eliminar(id: string, motivo: string | null): Promise<void> {
    await api.eliminarAsistente(id, motivo)
    asistentes.value = (asistentes.value ?? []).filter((a) => a.id !== id)
  }

  /** Al cambiar de cuenta no quedan datos de otro equipo en memoria. */
  function olvidar(): void {
    asistentes.value = null
  }

  return {
    asistentes,
    cargando,
    errorCarga,
    cargar,
    registrar,
    recuperar,
    restablecer,
    bloquear,
    desbloquear,
    eliminar,
    olvidar,
  }
})
