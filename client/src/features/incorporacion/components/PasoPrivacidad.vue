<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { Sesion, Usuario } from '@/features/acceso/types'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'

import { aceptarDocumentos, obtenerDocumentos } from '../api/incorporacion'
import type { DocumentoLegal, TipoDocumentoLegal } from '../types'
import LectorDocumento from './LectorDocumento.vue'

const props = defineProps<{ usuario: Usuario; contrasenaCambiada: boolean; saliendo: boolean }>()
const emit = defineEmits<{
  aceptada: [sesion: Sesion]
  salir: []
  recargar: []
  'sesion-terminada': []
}>()

interface Aviso {
  tono: 'error' | 'aviso'
  titulo: string
  mensaje: string
}

const documentos = ref<DocumentoLegal[]>([])
const cargando = ref(true)
const errorCarga = ref<string | null>(null)
// Cada casilla se marca a mano: nada se da por aceptado al abrir o leer los documentos.
const aceptados = ref<Record<TipoDocumentoLegal, boolean>>({ terminos: false, privacidad: false })
const errorCasillas = ref<string | null>(null)
const aviso = ref<Aviso | null>(null)
const enviando = ref(false)
const leyendo = ref<DocumentoLegal | null>(null)

const textos: Record<TipoDocumentoLegal, { acepto: string; detalle: string; leer: string }> = {
  terminos: {
    acepto: 'Acepto los términos de uso',
    detalle: 'Conozco las responsabilidades de mi rol y el funcionamiento de Deconsta.',
    leer: 'Leer los términos de uso',
  },
  privacidad: {
    acepto: 'He leído la política de privacidad y autorizo el tratamiento de mis datos descrito',
    detalle: 'Para gestionar mi cuenta y los documentos que registro en Deconsta.',
    leer: 'Leer la política de privacidad',
  },
}

const mapa = [
  {
    titulo: 'Quién ve la información',
    texto: 'Tu gerente y las asistentes de su equipo acceden a los documentos de su trabajo.',
    icono:
      'M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM21 19v-1a4 4 0 0 0-3-3.9M15.5 4.1a3 3 0 0 1 0 5.8',
  },
  {
    titulo: 'Para qué la usamos',
    texto: 'Organizar obligaciones, avisar vencimientos y dejar constancia de las decisiones.',
    icono: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6M9 17h4',
  },
  {
    titulo: 'Qué control conservas',
    texto: 'Puedes consultar y corregir tus datos y solicitar el ejercicio de tus derechos.',
    icono: 'M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z',
  },
]

const ORDEN: TipoDocumentoLegal[] = ['terminos', 'privacidad']

const todosMarcados = computed(() => documentos.value.every((d) => aceptados.value[d.tipo]))

async function cargar() {
  cargando.value = true
  errorCarga.value = null
  try {
    // Primero los términos y después la política, como en el prototipo.
    documentos.value = (await obtenerDocumentos()).sort(
      (a, b) => ORDEN.indexOf(a.tipo) - ORDEN.indexOf(b.tipo),
    )
    aceptados.value = { terminos: false, privacidad: false }
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    errorCarga.value =
      error instanceof ErrorApi ? error.message : 'No pudimos cargar los documentos.'
  } finally {
    cargando.value = false
  }
}

function mostrarError(error: unknown) {
  if (!(error instanceof ErrorApi)) {
    aviso.value = {
      tono: 'error',
      titulo: 'No pudimos registrar tu aceptación',
      mensaje: 'Ocurrió un error inesperado. Inténtalo de nuevo.',
    }
    return
  }
  switch (error.codigo) {
    case 'NO_AUTENTICADO':
      emit('sesion-terminada')
      return
    case 'INCORPORACION_PENDIENTE':
      emit('recargar')
      return
    case 'DOCUMENTOS_DESACTUALIZADOS':
      aviso.value = { tono: 'aviso', titulo: 'Hay una versión nueva', mensaje: error.message }
      void cargar()
      return
    default:
      aviso.value = {
        tono: 'error',
        titulo: 'No pudimos registrar tu aceptación',
        mensaje:
          error.campos.documentos ??
          (error.referencia ? `${error.message} Referencia: ${error.referencia}` : error.message),
      }
  }
}

async function enviar() {
  if (enviando.value || cargando.value) return
  aviso.value = null
  errorCasillas.value = todosMarcados.value ? null : 'Marca las dos casillas para continuar.'
  if (errorCasillas.value) return
  enviando.value = true
  try {
    const sesion = await aceptarDocumentos(
      documentos.value.map((d) => ({ tipo: d.tipo, version: d.version })),
    )
    emit('aceptada', sesion)
  } catch (error) {
    mostrarError(error)
  } finally {
    enviando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <section
    class="animate-aparecer rounded-[14px] border border-borde bg-white p-6 sm:p-9"
    aria-labelledby="titulo-privacidad"
  >
    <BaseAviso v-if="props.contrasenaCambiada" tono="exito" class="mb-6">
      Contraseña actualizada. Último paso: revisa cómo usamos tu información.
    </BaseAviso>

    <span
      aria-hidden="true"
      class="mb-5 grid size-12 place-items-center rounded-[13px] bg-acento-suave text-acento"
    >
      <svg
        viewBox="0 0 24 24"
        class="size-[22px] fill-none stroke-current stroke-2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3Z" />
      </svg>
    </span>
    <h1
      id="titulo-privacidad"
      class="text-[27px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[29px]"
    >
      Antes de empezar, tus datos.
    </h1>
    <p class="mt-3 mb-6 max-w-[620px] text-[13px] text-secundario">
      Hola, {{ usuario.nombres }}. Revisa cómo se usa tu información en Deconsta y acepta las
      condiciones para entrar a tu espacio.
    </p>

    <div
      class="grid gap-5 border-y border-borde py-6 sm:grid-cols-3 sm:gap-6"
      role="list"
      aria-label="Resumen del tratamiento de datos"
    >
      <div
        v-for="punto in mapa"
        :key="punto.titulo"
        role="listitem"
        class="grid grid-cols-[23px_1fr] gap-x-2.5 sm:block"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-[17px] fill-none stroke-acento stroke-2 sm:mb-2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path :d="punto.icono" />
        </svg>
        <h2 class="text-[12px] font-bold">{{ punto.titulo }}</h2>
        <p class="col-start-2 mt-1 text-[12px] leading-relaxed text-secundario">
          {{ punto.texto }}
        </p>
      </div>
    </div>

    <div
      v-if="cargando"
      class="flex items-center gap-2 py-8 text-[13px] text-secundario"
      role="status"
    >
      <span
        aria-hidden="true"
        class="size-4 animate-girar rounded-full border-2 border-acento border-t-transparent"
      />
      Cargando los documentos vigentes…
    </div>

    <div v-else-if="errorCarga" class="py-6">
      <BaseAviso tono="error" titulo="No pudimos cargar los documentos">{{ errorCarga }}</BaseAviso>
      <BaseBoton variante="secundario" class="mt-4" @click="cargar">Reintentar</BaseBoton>
    </div>

    <form v-else novalidate :aria-busy="enviando" @submit.prevent="enviar">
      <fieldset :aria-describedby="errorCasillas ? 'error-casillas' : undefined">
        <legend class="sr-only">Autorizaciones obligatorias</legend>
        <div
          v-for="documento in documentos"
          :key="documento.tipo"
          class="border-b border-borde py-5"
        >
          <label class="flex cursor-pointer items-start gap-2.5 text-[13px]">
            <input
              v-model="aceptados[documento.tipo]"
              type="checkbox"
              :name="documento.tipo"
              class="mt-0.5 size-[17px] shrink-0 cursor-pointer accent-acento"
              :aria-invalid="errorCasillas && !aceptados[documento.tipo] ? 'true' : undefined"
            />
            <span>
              <strong class="font-bold">{{ textos[documento.tipo].acepto }}</strong>
              <small class="mt-1 block text-[12px] text-secundario">
                {{ textos[documento.tipo].detalle }} Versión {{ documento.version }}.
              </small>
            </span>
          </label>
          <button
            type="button"
            class="mt-2 ml-[27px] rounded text-[12px] font-bold text-acento underline underline-offset-2 hover:text-acento-hover"
            @click="leyendo = documento"
          >
            {{ textos[documento.tipo].leer }}
          </button>
        </div>
      </fieldset>
      <p
        v-if="errorCasillas"
        id="error-casillas"
        role="alert"
        class="mt-3 animate-aparecer text-[12px] text-error"
      >
        {{ errorCasillas }}
      </p>

      <details class="mt-5 text-[12px] text-secundario">
        <summary class="cursor-pointer py-1.5 font-bold text-acento">
          Información legal y derechos sobre tus datos
        </summary>
        <p class="my-3 leading-relaxed">
          Conforme a la Ley N.° 29733, Ley de Protección de Datos Personales, puedes solicitar el
          acceso, la rectificación, la cancelación o la oposición al tratamiento de tus datos y
          revocar tu consentimiento.
        </p>
        <a
          href="https://www.gob.pe/9270"
          target="_blank"
          rel="noopener noreferrer"
          class="my-1.5 block text-acento underline underline-offset-2"
        >
          Conoce los derechos ARCO
        </a>
        <a
          href="https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus"
          target="_blank"
          rel="noopener noreferrer"
          class="my-1.5 block text-acento underline underline-offset-2"
        >
          Reglamento de la Ley N.° 29733
        </a>
      </details>

      <BaseAviso v-if="aviso" :tono="aviso.tono" :titulo="aviso.titulo" class="mt-5">
        {{ aviso.mensaje }}
      </BaseAviso>

      <div class="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
        <BaseBoton
          variante="discreto"
          :cargando="saliendo"
          :deshabilitado="enviando"
          @click="emit('salir')"
        >
          Salir de la sesión
        </BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando">
          {{ enviando ? 'Registrando…' : 'Aceptar y entrar a mi espacio' }}
          <svg
            v-if="!enviando"
            aria-hidden="true"
            viewBox="0 0 24 24"
            class="size-4 fill-none stroke-current stroke-2"
          >
            <path d="M5 12h14m-5-5 5 5-5 5" />
          </svg>
        </BaseBoton>
      </div>
    </form>

    <LectorDocumento :documento="leyendo" @cerrar="leyendo = null" />
  </section>
</template>
