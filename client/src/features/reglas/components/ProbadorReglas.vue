<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { evaluarDocumento } from '../api/reglas'
import { avisoImporte, filtrarImporte, normalizarImporte } from '../importes'
import type { Evaluacion } from '../types'

/**
 * Prueba las reglas con un documento de ejemplo, como si lo registrara una asistente. Quien decide
 * es el backend, con la misma evaluación que aplicará al registrar deudas. No guarda nada.
 */
const emit = defineEmits<{ 'sesion-terminada': [] }>()

const datos = reactive({ importe: '', titular: '' })
const errores = reactive<{ importe?: string }>({})
const resultado = ref<Evaluacion | null>(null)
const fallo = ref<string | null>(null)
const probando = ref(false)

// Un resultado deja de valer en cuanto cambian los datos.
watch(datos, () => {
  resultado.value = null
  delete errores.importe
})

async function probar() {
  fallo.value = null
  if (!normalizarImporte(datos.importe)) {
    errores.importe = 'Escribe el importe del documento.'
    return
  }
  probando.value = true
  try {
    resultado.value = await evaluarDocumento({
      importe: normalizarImporte(datos.importe),
      titular_nombre: datos.titular.trim() || null,
    })
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    if (error instanceof ErrorApi && error.campos.importe) errores.importe = error.campos.importe
    else fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
  } finally {
    probando.value = false
  }
}
</script>

<template>
  <section
    aria-labelledby="titulo-probador"
    class="rounded-[14px] border border-borde bg-white p-5"
  >
    <BaseIcono nombre="destello" class="size-6 text-acento" />
    <h2 id="titulo-probador" class="mt-3 text-[15px] font-extrabold">Prueba tus reglas.</h2>
    <p class="mt-1.5 text-[13px] text-secundario">
      Así decidirá Deconsta cuando tu asistente registre un documento. No se guarda nada.
    </p>
    <form class="mt-4" novalidate @submit.prevent="probar">
      <BaseCampo
        v-model="datos.importe"
        etiqueta="Importe del documento"
        prefijo="S/"
        modo-entrada="decimal"
        autocompletar="off"
        :filtro="filtrarImporte"
        :aviso="avisoImporte(datos.importe)"
        :error="errores.importe"
      />
      <BaseCampo
        v-model="datos.titular"
        etiqueta="Titular que figura (opcional)"
        autocompletar="off"
        :maximo="120"
        ayuda="Por ejemplo «PEREZ GOMEZ JUAN»."
      />
      <BaseBoton tipo="submit" variante="secundario" ancho="completo" :cargando="probando">
        Probar
      </BaseBoton>
    </form>

    <BaseAviso v-if="fallo" tono="error" class="mt-4">{{ fallo }}</BaseAviso>
    <div aria-live="polite">
      <div
        v-if="resultado"
        class="mt-4 animate-aparecer rounded-[10px] p-3.5 text-[13px]"
        :class="
          resultado.requiere_autorizacion
            ? 'bg-aviso-fondo text-aviso'
            : 'bg-exito-fondo text-exito'
        "
      >
        <p class="flex items-center gap-2 font-extrabold">
          <BaseIcono
            :nombre="resultado.requiere_autorizacion ? 'escudo' : 'check'"
            class="size-4"
          />
          {{ resultado.requiere_autorizacion ? 'Esperaría tu autorización' : 'Entraría directo' }}
        </p>
        <ul v-if="resultado.motivos.length" class="mt-2 flex list-disc flex-col gap-1 pl-5">
          <li v-for="motivo in resultado.motivos" :key="motivo.codigo">{{ motivo.detalle }}</li>
        </ul>
        <p v-else class="mt-1">
          {{
            resultado.titular_reconocido
              ? `Titular reconocido: ${resultado.titular_reconocido}.`
              : 'No hay titular que comparar y el importe no pide tu autorización.'
          }}
        </p>
      </div>
    </div>
  </section>
</template>
