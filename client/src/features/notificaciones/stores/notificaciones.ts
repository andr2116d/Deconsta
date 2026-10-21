import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import * as api from '../api/notificaciones'
import type { Notificacion } from '../types'

/**
 * Notificaciones de la cuenta. Las guarda el backend, así que sobreviven a recargas y cierres de
 * sesión; el flujo de eventos (SSE) solo avisa que hay una nueva y entonces se vuelve a pedir la
 * lista. Si el flujo se corta, el navegador se reconecta solo.
 */
export const useNotificacionesStore = defineStore('notificaciones', () => {
  const notificaciones = ref<Notificacion[] | null>(null)
  const noLeidas = ref(0)
  /** La última que llegó en tiempo real, para anunciarla. */
  const reciente = ref<Notificacion | null>(null)
  /** Sube con cada aviso en tiempo real: las pantallas lo observan para refrescarse. */
  const avisos = ref(0)
  const fuente = shallowRef<EventSource | null>(null)

  async function cargar(): Promise<void> {
    const bandeja = await api.listarNotificaciones()
    notificaciones.value = bandeja.notificaciones
    noLeidas.value = bandeja.no_leidas
  }

  async function alAvisar(evento: MessageEvent<string>) {
    try {
      await cargar()
    } catch {
      return
    }
    reciente.value = notificaciones.value?.find((n) => n.id === evento.data) ?? null
    avisos.value += 1
  }

  function conectar(): void {
    if (fuente.value || typeof EventSource === 'undefined') return
    const nueva = new EventSource(api.RUTA_FLUJO, { withCredentials: true })
    nueva.addEventListener(
      'notificacion',
      (evento) => void alAvisar(evento as MessageEvent<string>),
    )
    fuente.value = nueva
  }

  function desconectar(): void {
    fuente.value?.close()
    fuente.value = null
  }

  async function marcarLeida(id: string): Promise<void> {
    const notificacion = notificaciones.value?.find((n) => n.id === id)
    if (!notificacion || notificacion.leida) return
    await api.marcarLeida(id)
    notificacion.leida = true
    noLeidas.value = Math.max(0, noLeidas.value - 1)
  }

  async function marcarTodas(): Promise<void> {
    await api.marcarTodasLeidas()
    for (const notificacion of notificaciones.value ?? []) notificacion.leida = true
    noLeidas.value = 0
  }

  /** Al cerrar sesión no quedan avisos de otra cuenta ni la conexión abierta. */
  function olvidar(): void {
    desconectar()
    notificaciones.value = null
    noLeidas.value = 0
    reciente.value = null
  }

  return {
    notificaciones,
    noLeidas,
    reciente,
    avisos,
    cargar,
    conectar,
    desconectar,
    marcarLeida,
    marcarTodas,
    olvidar,
  }
})
