import { onBeforeUnmount, ref, shallowRef } from 'vue'

import { ErrorApi } from '@/shared/api/http'

import { consultarDocumento, subirDocumento } from '../api/deudas'
import type { Documento } from '../types'

export type Etapa = 'vacio' | 'subiendo' | 'analizando' | 'terminado' | 'error'

export const TAMANO_MAXIMO = 10 * 1024 * 1024
export const TIPOS_ACEPTADOS = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
const INTERVALO_MS = 1200
const ESPERA_MAXIMA_MS = 120_000

const espera = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms))

/** Revisión rápida antes de subir, para no esperar al servidor por un error evidente. */
export function errorArchivo(archivo: File): string | null {
  if (archivo.size === 0) return 'El archivo está vacío. Elige el documento otra vez.'
  if (archivo.size > TAMANO_MAXIMO)
    return 'El archivo supera los 10 MB. Sube una foto o un PDF más liviano.'
  if (!TIPOS_ACEPTADOS.includes(archivo.type))
    return 'Sube una imagen JPG, PNG o WebP, o un PDF del documento.'
  return null
}

/**
 * Sube un documento y espera su análisis consultando su estado. Cambiar de documento o salir de
 * la pantalla deja de esperar el anterior: su respuesta tardía nunca pisa al nuevo.
 */
export function useAnalisisDocumento() {
  const etapa = ref<Etapa>('vacio')
  const documento = ref<Documento | null>(null)
  const archivo = shallowRef<File | null>(null)
  const vistaPrevia = ref<string | null>(null)
  const error = shallowRef<ErrorApi | null>(null)
  let turno = 0

  function liberarVista() {
    if (vistaPrevia.value) URL.revokeObjectURL(vistaPrevia.value)
    vistaPrevia.value = null
  }

  function reiniciar() {
    turno += 1
    liberarVista()
    etapa.value = 'vacio'
    documento.value = null
    archivo.value = null
    error.value = null
  }

  function fallar(causa: unknown) {
    error.value =
      causa instanceof ErrorApi
        ? causa
        : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
    etapa.value = 'error'
  }

  async function esperarAnalisis(id: string, propio: number) {
    const limite = Date.now() + ESPERA_MAXIMA_MS
    while (turno === propio && Date.now() < limite) {
      await espera(INTERVALO_MS)
      if (turno !== propio) return
      const actual = await consultarDocumento(id)
      if (turno !== propio) return
      documento.value = actual
      if (actual.estado !== 'analizando') {
        etapa.value = 'terminado'
        return
      }
    }
    if (turno === propio) {
      fallar(
        new ErrorApi(0, {
          code: 'ANALISIS_DEMORADO',
          detail: 'La revisión del documento está tardando más de lo normal. Súbelo otra vez.',
        }),
      )
    }
  }

  async function cargar(nuevo: File) {
    reiniciar()
    const propio = turno
    archivo.value = nuevo
    vistaPrevia.value = URL.createObjectURL(nuevo)
    const local = errorArchivo(nuevo)
    if (local) {
      fallar(new ErrorApi(422, { code: 'ARCHIVO_INVALIDO', detail: local }))
      return
    }
    etapa.value = 'subiendo'
    try {
      const subido = await subirDocumento(nuevo)
      if (turno !== propio) return
      documento.value = subido
      etapa.value = subido.estado === 'analizando' ? 'analizando' : 'terminado'
      if (subido.estado === 'analizando') await esperarAnalisis(subido.id, propio)
    } catch (causa) {
      if (turno === propio) fallar(causa)
    }
  }

  onBeforeUnmount(reiniciar)

  return { etapa, documento, archivo, vistaPrevia, error, cargar, reiniciar }
}
