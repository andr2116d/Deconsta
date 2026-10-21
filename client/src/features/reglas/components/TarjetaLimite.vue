<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { avisoImporte, filtrarImporte, formatearSoles, normalizarImporte } from '../importes'
import { useReglasStore } from '../stores/reglas'
import DialogoConfirmarRegla from './DialogoConfirmarRegla.vue'

/** El límite en soles: por encima de él, lo que registra una asistente espera tu autorización. */
const emit = defineEmits<{ guardado: [mensaje: string]; 'sesion-terminada': [] }>()

const store = useReglasStore()
const actual = computed(() => store.reglas?.limite_importe ?? null)
const valor = ref('')
const errores = reactive<{ limite_importe?: string }>({})
const fallo = ref<ErrorApi | null>(null)
const enviando = ref(false)
const confirmarQuitar = ref(false)

watch(actual, (limite) => (valor.value = limite ?? ''), { immediate: true })
watch(valor, () => delete errores.limite_importe)

const aviso = computed(() =>
  !valor.value && actual.value
    ? 'Escribe un importe, o usa «Quitar límite» si ya no quieres uno.'
    : avisoImporte(valor.value),
)

// Guardar solo se activa con un importe distinto del vigente.
const hayCambio = computed(() => {
  const nuevo = normalizarImporte(valor.value)
  return nuevo !== '' && Number(nuevo) !== Number(actual.value ?? NaN)
})

function mostrarFallo(error: unknown) {
  const comoApi =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
  if (comoApi.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return
  }
  if (comoApi.campos.limite_importe) errores.limite_importe = comoApi.campos.limite_importe
  else fallo.value = comoApi
}

async function guardar(limite: string | null) {
  fallo.value = null
  if (limite !== null && !normalizarImporte(limite)) {
    errores.limite_importe = 'Escribe el límite en soles.'
    return
  }
  enviando.value = true
  try {
    const reglas = await store.cambiarLimite(limite === null ? null : normalizarImporte(limite))
    emit(
      'guardado',
      reglas.limite_importe
        ? `Guardaste tu límite: lo que tus asistentes registren por más de ${formatearSoles(reglas.limite_importe)} esperará tu autorización.`
        : 'Quitaste el límite: el importe ya no detiene lo que registren tus asistentes.',
    )
  } catch (error) {
    mostrarFallo(error)
  } finally {
    enviando.value = false
    confirmarQuitar.value = false
  }
}
</script>

<template>
  <section
    aria-labelledby="titulo-limite"
    class="rounded-[14px] border border-borde bg-white p-5 sm:p-6"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 id="titulo-limite" class="text-[17px] font-extrabold">Autorización por importe</h2>
        <p class="mt-1 max-w-[52ch] text-[13px] text-secundario">
          Lo que tus asistentes registren por más de este importe esperará tu autorización antes de
          pagarse. Lo que registras tú entra directo.
        </p>
      </div>
      <span
        class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-bold"
        :class="actual ? 'bg-exito-fondo text-exito' : 'bg-fondo text-secundario'"
      >
        <span aria-hidden="true" class="size-1.5 rounded-full bg-current" />
        {{ actual ? `Límite de ${formatearSoles(actual)}` : 'Sin límite' }}
      </span>
    </div>

    <form class="mt-5" novalidate @submit.prevent="guardar(valor)">
      <BaseCampo
        v-model="valor"
        etiqueta="Pedir autorización si el importe supera"
        prefijo="S/"
        modo-entrada="decimal"
        autocompletar="off"
        :filtro="filtrarImporte"
        :aviso="aviso"
        :error="errores.limite_importe"
        :ayuda="
          actual
            ? 'Un importe igual al límite no la pide.'
            : 'Sin límite, el importe no detiene ninguna deuda; el titular se sigue revisando.'
        "
      />
      <BaseAviso v-if="fallo" tono="error" titulo="No pudimos guardar el límite" class="mb-4">
        {{ fallo.message }}
      </BaseAviso>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
        <BaseBoton
          v-if="actual"
          variante="discreto"
          :deshabilitado="enviando"
          @click="confirmarQuitar = true"
        >
          <BaseIcono nombre="cerrar" class="size-4" />
          Quitar límite
        </BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando" :deshabilitado="!hayCambio">
          Guardar límite
        </BaseBoton>
      </div>
    </form>

    <DialogoConfirmarRegla
      :abierto="confirmarQuitar"
      titulo="¿Quitar el límite de importe?"
      :puntos="[
        'Lo que registren tus asistentes ya no esperará tu autorización por su importe.',
        'Los documentos de otros titulares seguirán pidiéndola.',
      ]"
      confirmar="Quitar límite"
      :enviando="enviando"
      @confirmar="guardar(null)"
      @cancelar="confirmarQuitar = false"
    />
  </section>
</template>
