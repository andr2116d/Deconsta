<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import BaseIcono from '@/shared/components/BaseIcono.vue'

// Cada pantalla dice desde qué rol se trabaja y cuál es su responsabilidad (DECONSTA/DESIGN.md).
const props = defineProps<{ rol: Rol }>()

const contexto = computed(() =>
  props.rol === 'gerente'
    ? {
        sello: 'Gerencia',
        icono: 'escudo' as const,
        texto: 'Tú autorizas las deudas y verificas los pagos.',
      }
    : {
        sello: 'Asistencia',
        icono: 'documento' as const,
        texto: 'Tú registras las deudas y completas los pagos que te asignan.',
      },
)
</script>

<template>
  <div
    class="mb-6 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-borde pb-4 text-[13px] text-secundario sm:mb-8"
  >
    <span
      class="inline-flex items-center gap-1.5 rounded-md bg-acento px-2.5 py-1 text-[12px] font-bold text-white"
    >
      <BaseIcono :nombre="contexto.icono" class="size-3.5" />
      {{ contexto.sello }}
    </span>
    <span class="min-w-0 flex-1 basis-56">{{ contexto.texto }}</span>
    <RouterLink
      :to="{ name: 'permisos' }"
      class="inline-flex min-h-8 items-center gap-1 rounded-md text-[12px] font-bold text-acento hover:underline"
    >
      Ver mis permisos
      <BaseIcono nombre="derecha" class="size-3.5" />
    </RouterLink>
  </div>
</template>
