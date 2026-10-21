<script setup lang="ts">
import { computed } from 'vue'

import type { PasoPendiente, Usuario } from '@/features/acceso/types'

const props = defineProps<{ usuario: Usuario; pasoActual: PasoPendiente | null }>()

const iniciales = computed(() => props.usuario.nombres.slice(0, 1).toUpperCase())
const rol = computed(() => (props.usuario.rol === 'gerente' ? 'Gerente' : 'Asistente'))

// El acceso ya se completó al validar las credenciales. La contraseña temporal no es un paso: se
// recuerda dentro del espacio.
const pasos = computed(() => [
  { nombre: 'Acceso', completo: true, actual: false },
  {
    nombre: 'Privacidad',
    completo: false,
    actual: props.pasoActual === 'aceptar_documentos',
  },
])
</script>

<template>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-4 text-[12px]">
    <span
      aria-hidden="true"
      class="grid size-[34px] shrink-0 place-items-center rounded-full bg-acento-suave text-[11px] font-extrabold text-acento"
    >
      {{ iniciales }}
    </span>
    <span class="leading-tight">
      <strong class="block font-bold">{{ usuario.nombres }}</strong>
      <small class="text-[11px] text-secundario">{{ rol }}</small>
    </span>
    <ol
      aria-label="Pasos de tu primer ingreso"
      class="flex items-center gap-2 text-[11px] text-secundario sm:ml-auto"
    >
      <li
        v-for="(paso, indice) in pasos"
        :key="paso.nombre"
        class="flex items-center gap-1.5"
        :class="paso.actual ? 'font-bold text-tinta' : ''"
        :aria-current="paso.actual ? 'step' : undefined"
      >
        <span v-if="indice > 0" aria-hidden="true" class="h-px w-4 bg-borde" />
        <svg
          v-if="paso.completo"
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-3.5 fill-none stroke-acento stroke-[2.5]"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="m5 12 4.5 4.5L19 7" />
        </svg>
        <span
          v-else
          aria-hidden="true"
          class="size-2 rounded-full"
          :class="paso.actual ? 'bg-acento' : 'bg-borde'"
        />
        {{ paso.nombre }}
        <span class="sr-only">{{
          paso.completo ? '(completado)' : paso.actual ? '(en curso)' : '(pendiente)'
        }}</span>
      </li>
    </ol>
  </div>
</template>
