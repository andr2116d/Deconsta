<script setup lang="ts">
import { computed } from 'vue'

import type { Requisito } from '../composables/useSeguridadContrasena'

const props = defineProps<{
  puntaje: number
  nivel: string
  requisitos: Requisito[]
  visible: boolean
}>()

const colores = ['bg-error', 'bg-error', 'bg-aviso', 'bg-exito', 'bg-exito']
const colorTexto = computed(() =>
  props.puntaje >= 3 ? 'text-exito' : props.puntaje === 2 ? 'text-aviso' : 'text-error',
)
</script>

<template>
  <div class="mt-1">
    <div
      role="meter"
      aria-label="Seguridad de la nueva contraseña"
      aria-valuemin="0"
      aria-valuemax="4"
      :aria-valuenow="puntaje"
      :aria-valuetext="visible ? nivel : 'Sin contraseña'"
      class="grid grid-cols-4 gap-1"
    >
      <span
        v-for="n in 4"
        :key="n"
        class="h-1.5 rounded-full transition-colors duration-200"
        :class="visible && puntaje >= n ? colores[puntaje] : 'bg-borde'"
      />
    </div>
    <p class="mt-1.5 text-[12px]" aria-live="polite">
      <span class="text-secundario">Seguridad: </span>
      <strong :class="visible ? colorTexto : 'text-secundario'">{{ visible ? nivel : '—' }}</strong>
    </p>
    <ul class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[12px]">
      <li
        v-for="requisito in requisitos"
        :key="requisito.clave"
        class="flex items-center gap-1.5 transition-colors duration-200"
        :class="requisito.cumplido ? 'text-exito' : 'text-secundario'"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-3.5 shrink-0 fill-none stroke-current stroke-[2.5]"
        >
          <path v-if="requisito.cumplido" d="m5 12 4.5 4.5L19 7" />
          <circle v-else cx="12" cy="12" r="4" />
        </svg>
        {{ requisito.texto }}
        <span class="sr-only">{{ requisito.cumplido ? '(cumplido)' : '(pendiente)' }}</span>
      </li>
    </ul>
  </div>
</template>
