import { onBeforeUnmount, ref, shallowRef } from 'vue'

import { ErrorApi } from '@/shared/api/http'

import { consultarDocumento, subirDocumento } from '../api/deudas'
import type { Documento } from '../types'

export type Etapa = 'vacio' | 'subiendo' | 'analizando' | 'terminado' | 'error'

export const TAMANO_MAXIMO = 10 * 1024 * 1024
export const TIPOS_ACEPTADOS = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
const EXTENSIONES_ACEPTADAS = ['pdf', 'jpg', 'jpeg', 'png', 'webp']
/** Para el selector de archivos: por tipo y por extensión, por si el sistema no informa el tipo. */
export const ACEPTAR = [...TIPOS_ACEPTADOS, ...EXTENSIONES_ACEPTADAS.map((e) => `.${e}`)].join(',')
const extension = (nombre: string) => nombre.split('.').pop()?.toLowerCase() ?? ''
const INTERVALO_MS = 1200
// La lectura y la revisión con IA tardan de segundos a medio minuto, más si hay otros documentos
// en cola. Desde DEMORA_MS se avisa que está tardando; a los 3 minutos se deja de esperar.
const DEMORA_MS = 20_000
const ESPERA_MAXIMA_MS = 180_000

const espera = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms))

/**
 * Revisión rápida antes de subir, para no esperar al servidor por un error evidente. Algunos
 * sistemas no informan el tipo del archivo: entonces vale su extensión. El backend lo decide por
 * su contenido.
 */
export function errorArchivo(archivo: File): string | null {
  if (archivo.size === 0) return 'El archivo está vacío. Elige el documento otra vez.'
  if (archivo.size > TAMANO_MAXIMO) {
    const megas = (archivo.size / 1024 / 1024).toFixed(1)
    return `El archivo pesa ${megas} MB y el máximo es 10 MB. Sube una foto o un PDF más liviano.`
  }
  const ext = extension(archivo.name)
  if (['heic', 'heif'].includes(ext) || /image\/hei[cf]/.test(archivo.type))
    return 'Las fotos HEIC del iPhone aún no se aceptan. Compártela como JPG (o toma una captura) y vuelve a subirla.'
  const aceptado = archivo.type
    ? TIPOS_ACEPTADOS.includes(archivo.type)
    : EXTENSIONES_ACEPTADAS.includes(ext)
  if (!aceptado) return 'Sube una imagen JPG, PNG o WebP, o un PDF del documento.'
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
  /** El análisis está tardando más de lo habitual. */
  const demorado = ref(false)
  let turno = 0

  function liberarVista() {
    if (vistaPrevia.value) URL.revokeObjectURL(vistaPrevia.value)
    vistaPrevia.value = null
  }

  function reiniciar() {
    turno += 1
    liberarVista()
    etapa.value = 'vacio'
    demorado.value = false
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
    const inicio = Date.now()
    while (turno === propio && Date.now() - inicio < ESPERA_MAXIMA_MS) {
      await espera(INTERVALO_MS)
      if (turno !== propio) return
      demorado.value = Date.now() - inicio >= DEMORA_MS
      let actual: Documento
      try {
        actual = await consultarDocumento(id)
      } catch (causa) {
        // Un corte de red o del servidor no pierde el documento: se vuelve a consultar.
        const pasajero = causa instanceof ErrorApi && (causa.estado === 0 || causa.estado >= 500)
        if (pasajero) continue
        throw causa
      }
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

  return { etapa, documento, archivo, vistaPrevia, error, demorado, cargar, reiniciar }
}
