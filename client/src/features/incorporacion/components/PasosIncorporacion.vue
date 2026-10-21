<script setup lang="ts">
import { computed } from 'vue'

import type { Usuario } from '@/features/acceso/types'

import type { Etapa } from '../types'

const props = defineProps<{ usuario: Usuario; etapa: Etapa | null; conDatos: boolean }>()

const iniciales = computed(() => props.usuario.nombres.slice(0, 1).toUpperCase())
const rol = computed(() => (props.usuario.rol === 'gerente' ? 'Gerente' : 'Asistente'))

// El acceso ya se completó al validar las credenciales. Una asistente nueva suma la contraseña
// (recomendada) y la confirmación de sus datos (obligatoria).
const pasos = computed(() => {
  const orden: Etapa[] = props.conDatos ? ['privacidad', 'contrasena', 'datos'] : ['privacidad']
  const nombres: Record<Etapa, string> = {
    privacidad: 'Privacidad',
    contrasena: 'Contraseña',
    datos: 'Tus datos',
  }
  const actual = props.etapa ? orden.indexOf(props.etapa) : orden.length
  return [
    { nombre: 'Acceso', completo: true, actual: false },
    ...orden.map((etapa, indice) => ({
      nombre: nombres[etapa],
      completo: indice < actual,
      actual: indice === actual,
    })),
  ]
})
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
      class="flex flex-wrap items-center gap-2 text-[11px] text-secundario sm:ml-auto"
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
          class="size-2 rounded-full transition-colors duration-200"
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
