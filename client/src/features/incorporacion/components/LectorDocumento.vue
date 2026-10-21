<script setup lang="ts">
import { computed } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'

import type { DocumentoLegal } from '../types'

// Solo lectura: abrir o cerrar el documento no lo da por aceptado.
const props = defineProps<{ documento: DocumentoLegal | null }>()
const emit = defineEmits<{ cerrar: [] }>()

const fecha = new Intl.DateTimeFormat('es-PE', { dateStyle: 'long', timeZone: 'America/Lima' })
const vigencia = computed(() =>
  props.documento ? fecha.format(new Date(props.documento.vigente_desde)) : '',
)
</script>

<template>
  <BaseDialogo
    :abierto="documento !== null"
    :titulo="documento?.titulo ?? ''"
    ancho="amplio"
    @cerrar="emit('cerrar')"
  >
    <template #icono>
      <svg
        viewBox="0 0 24 24"
        class="size-5 fill-none stroke-current stroke-2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6M9 17h4"
        />
      </svg>
    </template>
    <template v-if="documento">
      <p class="mt-1 text-[12px] text-secundario">
        Versión {{ documento.version }} · vigente desde el {{ vigencia }}
      </p>
      <div
        tabindex="0"
        aria-label="Contenido del documento"
        class="mt-5 max-h-[55dvh] overflow-y-auto border-y border-borde py-4 pr-1"
      >
        <section
          v-for="seccion in documento.secciones"
          :key="seccion.titulo"
          class="mb-5 last:mb-0"
        >
          <h3 class="mb-1.5 text-[14px] font-bold">{{ seccion.titulo }}</h3>
          <p
            v-for="(parrafo, indice) in seccion.parrafos"
            :key="indice"
            class="mb-2 text-[13px] leading-relaxed text-secundario last:mb-0"
          >
            {{ parrafo }}
          </p>
        </section>
      </div>
      <div class="mt-5 flex justify-end">
        <BaseBoton variante="secundario" @click="emit('cerrar')">Cerrar</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
