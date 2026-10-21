<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { ACEPTAR, type Etapa } from '../composables/useAnalisisDocumento'

/**
 * Escenario del documento: se suelta o se elige el archivo, se ve tal cual se subió y, mientras
 * se revisa, una animación de lectura que respeta la preferencia de movimiento reducido.
 */
const props = defineProps<{
  etapa: Etapa
  archivo: File | null
  vistaPrevia: string | null
  /** Ya no se puede cambiar (la deuda se registró). */
  bloqueado?: boolean
}>()
const emit = defineEmits<{ elegir: [archivo: File]; cambiar: [] }>()

const entrada = ref<HTMLInputElement>()
const encima = ref(false)
const idAyuda = useId()

const esPdf = computed(
  () => props.archivo?.type === 'application/pdf' || /\.pdf$/i.test(props.archivo?.name ?? ''),
)
const trabajando = computed(() => props.etapa === 'subiendo' || props.etapa === 'analizando')
const tamano = computed(() => {
  const bytes = props.archivo?.size ?? 0
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
})

function tomar(lista: FileList | null | undefined) {
  const archivo = lista?.[0]
  if (archivo) emit('elegir', archivo)
}

function alSoltar(evento: DragEvent) {
  encima.value = false
  tomar(evento.dataTransfer?.files)
}

function alElegir(evento: Event) {
  const elemento = evento.target as HTMLInputElement
  tomar(elemento.files)
  // Permite volver a elegir el mismo archivo después de cambiarlo.
  elemento.value = ''
}
</script>

<template>
  <div
    class="relative flex min-h-[300px] flex-col items-center justify-center overflow-hidden rounded-[14px] bg-[#ede8ed] p-5 sm:p-6 lg:sticky lg:top-[156px] lg:min-h-[520px]"
  >
    <input
      ref="entrada"
      type="file"
      class="sr-only"
      tabindex="-1"
      aria-hidden="true"
      :accept="ACEPTAR"
      @change="alElegir"
    />

    <div
      v-if="!archivo"
      class="flex min-h-[260px] w-full flex-col items-center justify-center rounded-xl border border-dashed p-6 text-center transition-colors duration-200 lg:min-h-[340px]"
      :class="encima ? 'border-acento bg-acento-suave' : 'border-[#ad96a6] bg-[#f5f0f4]'"
      @dragenter.prevent="encima = true"
      @dragover.prevent="encima = true"
      @dragleave.prevent="encima = false"
      @drop.prevent="alSoltar"
    >
      <span
        aria-hidden="true"
        class="mb-4 grid size-[52px] place-items-center rounded-[15px] bg-white text-acento"
      >
        <BaseIcono nombre="documento" class="size-6" />
      </span>
      <h2 class="text-[17px] font-extrabold">Suelta aquí el recibo</h2>
      <p :id="idAyuda" class="mt-2 mb-5 max-w-[260px] text-[12px] text-secundario">
        Foto o PDF de hasta 10 MB: recibo, boleta, factura, cronograma o papeleta. Que se lea
        completo.
      </p>
      <BaseBoton :aria-describedby="idAyuda" @click="entrada?.click()">Elegir archivo</BaseBoton>
    </div>

    <template v-else>
      <div class="relative flex w-full flex-1 items-center justify-center">
        <img
          v-if="vistaPrevia && !esPdf"
          :src="vistaPrevia"
          alt="Documento que subiste"
          class="max-h-[420px] max-w-full rounded-[4px] object-contain shadow-[0_9px_30px_#30233024]"
        />
        <object
          v-else-if="vistaPrevia"
          :data="vistaPrevia"
          type="application/pdf"
          class="h-[420px] w-full rounded-[4px] bg-white shadow-[0_9px_30px_#30233024]"
          aria-label="Documento que subiste"
        >
          <p class="p-6 text-center text-[12px] text-secundario">
            Tu navegador no muestra el PDF aquí, pero ya lo tenemos.
          </p>
        </object>

        <Transition name="vista">
          <div
            v-if="trabajando"
            class="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-lg bg-[#ede8eddd] px-6 text-center"
            role="status"
            aria-live="polite"
          >
            <span aria-hidden="true" class="relative block h-24 w-20 rounded-[4px] bg-white shadow">
              <span class="linea-lectura absolute inset-x-2 h-0.5 rounded bg-acento" />
              <span class="absolute inset-x-3 top-4 h-1 rounded bg-borde" />
              <span class="absolute inset-x-3 top-8 h-1 w-10 rounded bg-borde" />
              <span class="absolute inset-x-3 top-12 h-1 rounded bg-borde" />
              <span class="absolute right-3 bottom-4 h-2 w-8 rounded bg-rosa" />
            </span>
            <b class="text-[13px]">
              {{ etapa === 'subiendo' ? 'Subiendo el documento…' : 'Revisando el documento…' }}
            </b>
            <p class="max-w-[260px] text-[12px] text-secundario">
              Leemos el texto, lo contrastamos y revisamos que el archivo no esté editado.
            </p>
          </div>
        </Transition>
      </div>

      <p class="mt-5 flex max-w-full items-center gap-2 text-[12px] text-secundario">
        <BaseIcono nombre="documento" class="size-4" />
        <span class="truncate">{{ archivo.name }}</span>
        <span class="shrink-0">· {{ tamano }}</span>
      </p>
      <BaseBoton
        v-if="!bloqueado"
        variante="discreto"
        class="mt-1"
        :deshabilitado="trabajando"
        @click="emit('cambiar')"
      >
        Cambiar documento
      </BaseBoton>
    </template>
  </div>
</template>

<style scoped>
.linea-lectura {
  animation: leer 1.6s ease-in-out infinite;
}

@keyframes leer {
  0%,
  100% {
    top: 10%;
  }
  50% {
    top: 85%;
  }
}
</style>
