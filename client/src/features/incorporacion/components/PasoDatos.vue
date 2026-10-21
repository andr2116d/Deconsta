<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'

import type { Sesion } from '@/features/acceso/types'
import { obtenerCuenta } from '@/features/cuenta/api/cuenta'
import { ErrorApi } from '@/shared/api/http'
import { useLimpiarErrores } from '@/shared/composables/useLimpiarErrores'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import CampoDocumento from '@/shared/components/CampoDocumento.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'
import {
  avisoCelular,
  avisoCorreo,
  celularValido,
  correoValido,
  documentoValido,
  filtrarCelular,
  filtrarCorreo,
  filtrarNombre,
  type TipoDocumento,
} from '@/shared/validaciones/persona'

import { confirmarDatos } from '../api/incorporacion'

// Paso obligatorio de una asistente nueva: completa su correo y revisa lo que registró su gerente.
// Es la primera confirmación, así que aún puede corregir su documento.
const emit = defineEmits<{ confirmada: [sesion: Sesion]; 'sesion-terminada': []; recargar: [] }>()

type Campo = 'nombres' | 'apellidos' | 'correo' | 'telefono' | 'numero_documento' | 'confirmo'

const ETIQUETAS: Record<string, string> = {
  nombres: 'Nombres',
  apellidos: 'Apellidos',
  correo: 'Correo',
  telefono: 'Celular',
  numero_documento: 'Documento',
}

const formulario = ref<HTMLFormElement>()
const datos = reactive({
  nombres: '',
  apellidos: '',
  correo: '',
  telefono: '',
  tipo_documento: 'dni' as TipoDocumento,
  numero_documento: '',
})
const confirmo = ref(false)
const errores = reactive<Partial<Record<Campo, string>>>({})
const cargando = ref(true)
const errorCarga = ref<string | null>(null)
const enviando = ref(false)
useLimpiarErrores(datos, errores)
const fallo = ref<ErrorApi | null>(null)

function sesionTerminada(error: unknown): boolean {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return true
  }
  return false
}

async function cargar() {
  cargando.value = true
  errorCarga.value = null
  try {
    const cuenta = await obtenerCuenta()
    Object.assign(datos, {
      nombres: cuenta.nombres,
      apellidos: cuenta.apellidos,
      correo: cuenta.correo ?? '',
      telefono: cuenta.telefono ?? '',
      tipo_documento: cuenta.tipo_documento,
      numero_documento: cuenta.numero_documento,
    })
  } catch (error) {
    if (sesionTerminada(error)) return
    errorCarga.value = error instanceof ErrorApi ? error.message : 'No pudimos cargar tus datos.'
  } finally {
    cargando.value = false
  }
}

async function enfocarPrimerError() {
  await nextTick()
  formulario.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

function validar(): boolean {
  for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
  if (!datos.nombres.trim()) errores.nombres = 'Escribe tus nombres.'
  if (!datos.apellidos.trim()) errores.apellidos = 'Escribe tus apellidos.'
  if (!datos.correo) errores.correo = 'Escribe tu correo.'
  else if (!correoValido(datos.correo)) errores.correo = avisoCorreo(datos.correo)
  if (!celularValido(datos.telefono)) {
    errores.telefono = 'Escribe un celular de 9 dígitos que empiece con 9.'
  }
  if (!documentoValido(datos.tipo_documento, datos.numero_documento)) {
    errores.numero_documento =
      datos.tipo_documento === 'dni'
        ? 'El DNI debe tener 8 dígitos.'
        : 'El carné debe tener de 9 a 12 letras o dígitos.'
  }
  if (!confirmo.value) errores.confirmo = 'Marca la casilla para confirmar tus datos.'
  return Object.keys(errores).length === 0
}

async function enviar() {
  if (enviando.value || cargando.value) return
  if (!validar()) {
    enfocarPrimerError()
    return
  }
  fallo.value = null
  enviando.value = true
  try {
    emit('confirmada', await confirmarDatos({ ...datos }))
  } catch (error) {
    if (sesionTerminada(error)) return
    if (
      error instanceof ErrorApi &&
      ['INCORPORACION_PENDIENTE', 'DATOS_YA_CONFIRMADOS'].includes(error.codigo)
    ) {
      emit('recargar')
      return
    }
    const comoApi =
      error instanceof ErrorApi
        ? error
        : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
    Object.assign(errores, comoApi.campos)
    fallo.value = comoApi
  } finally {
    enviando.value = false
  }
}

function cerrarFallo() {
  fallo.value = null
  enfocarPrimerError()
}

onMounted(cargar)
</script>

<template>
  <section
    class="animate-aparecer rounded-[14px] border border-borde bg-white p-6 sm:p-9"
    aria-labelledby="titulo-datos"
    :aria-busy="cargando"
  >
    <span
      aria-hidden="true"
      class="mb-5 grid size-12 place-items-center rounded-[13px] bg-acento-suave text-acento"
    >
      <BaseIcono nombre="persona" class="size-[22px]" />
    </span>
    <h1
      id="titulo-datos"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[30px]"
    >
      Confirma tus datos.
    </h1>
    <p class="mt-2 mb-6 max-w-[60ch] text-[13px] text-secundario">
      Tu gerente registró algunos de tus datos. Revísalos, corrígelos si hace falta y completa tu
      correo. Es el último paso para entrar a tu espacio.
    </p>

    <div v-if="errorCarga" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" class="w-full">{{ errorCarga }}</BaseAviso>
      <BaseBoton variante="secundario" @click="cargar">Reintentar</BaseBoton>
    </div>
    <div
      v-else-if="cargando"
      aria-hidden="true"
      class="grid gap-4 motion-safe:animate-pulse sm:grid-cols-2"
    >
      <div v-for="n in 4" :key="n" class="h-[70px] rounded-[7px] bg-fondo" />
    </div>

    <form v-else ref="formulario" novalidate :aria-busy="enviando" @submit.prevent="enviar">
      <div class="grid gap-x-5 sm:grid-cols-2">
        <BaseCampo
          v-model="datos.nombres"
          etiqueta="Nombres"
          autocompletar="given-name"
          capitalizar
          :maximo="80"
          :filtro="filtrarNombre"
          :error="errores.nombres"
        />
        <BaseCampo
          v-model="datos.apellidos"
          etiqueta="Apellidos"
          autocompletar="family-name"
          capitalizar
          :maximo="80"
          :filtro="filtrarNombre"
          :error="errores.apellidos"
        />
        <BaseCampo
          v-model="datos.correo"
          etiqueta="Correo"
          tipo="email"
          autocompletar="email"
          modo-entrada="email"
          :maximo="254"
          :filtro="filtrarCorreo"
          :aviso="avisoCorreo(datos.correo)"
          :error="errores.correo"
        />
        <BaseCampo
          v-model="datos.telefono"
          etiqueta="Celular"
          tipo="tel"
          autocompletar="tel-national"
          modo-entrada="numeric"
          prefijo="+51"
          :filtro="filtrarCelular"
          :aviso="avisoCelular(datos.telefono)"
          :error="errores.telefono"
        />
      </div>
      <CampoDocumento
        v-model:tipo="datos.tipo_documento"
        v-model:numero="datos.numero_documento"
        :error="errores.numero_documento"
        ayuda="Revísalo con cuidado: después de confirmarlo ya no podrás cambiar el número."
      />

      <label
        class="mt-2 flex cursor-pointer items-start gap-3 rounded-[10px] border p-4 transition-colors duration-200"
        :class="errores.confirmo ? 'border-error' : 'border-borde hover:border-control'"
      >
        <input
          v-model="confirmo"
          type="checkbox"
          class="mt-0.5 size-4 accent-[var(--color-acento)]"
          :aria-invalid="errores.confirmo ? 'true' : undefined"
        />
        <span class="text-[13px]">
          Confirmo que estos datos son correctos y me pertenecen.
          <span v-if="errores.confirmo" class="mt-1 block text-[12px] text-error">
            {{ errores.confirmo }}
          </span>
        </span>
      </label>

      <div class="mt-6 flex justify-end">
        <BaseBoton tipo="submit" :cargando="enviando">
          {{ enviando ? 'Guardando…' : 'Confirmar mis datos' }}
        </BaseBoton>
      </div>
    </form>

    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos guardar tus datos"
      :etiquetas="ETIQUETAS"
      @cerrar="cerrarFallo"
      @reintentar="enviar"
    />
  </section>
</template>
