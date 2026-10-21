<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import BaseIcono from '@/shared/components/BaseIcono.vue'

import { useNotificacionesStore } from '../stores/notificaciones'
import type { Notificacion } from '../types'

/** Anuncia la notificación que acaba de llegar en tiempo real, sin quitar el foco. */
const store = useNotificacionesStore()
const visible = ref<Notificacion | null>(null)
let temporizador: ReturnType<typeof setTimeout> | undefined

watch(
  () => store.avisos,
  () => {
    if (!store.reciente) return
    visible.value = store.reciente
    clearTimeout(temporizador)
    temporizador = setTimeout(() => (visible.value = null), 8000)
  },
)
onBeforeUnmount(() => clearTimeout(temporizador))
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-4 bottom-4 z-40 flex justify-center sm:inset-x-auto sm:right-6 sm:bottom-6"
    role="status"
    aria-live="polite"
  >
    <Transition name="vista">
      <div
        v-if="visible"
        class="pointer-events-auto flex w-full max-w-[380px] items-start gap-3 rounded-[14px] border border-borde bg-white p-4 shadow-[0_20px_60px_#30233026]"
      >
        <span
          aria-hidden="true"
          class="grid size-9 shrink-0 place-items-center rounded-full bg-acento-suave text-acento"
        >
          <BaseIcono nombre="avisos" class="size-[18px]" />
        </span>
        <div class="min-w-0 flex-1">
          <strong class="block text-[13px]">{{ visible.titulo }}</strong>
          <p class="mt-0.5 line-clamp-2 text-[12px] text-secundario">{{ visible.cuerpo }}</p>
          <RouterLink
            :to="{ name: 'notificaciones' }"
            class="mt-1.5 inline-block text-[12px] font-bold text-acento hover:underline"
            @click="visible = null"
          >
            Ver avisos
          </RouterLink>
        </div>
        <button
          type="button"
          class="grid size-8 shrink-0 place-items-center rounded-lg text-secundario hover:bg-fondo"
          aria-label="Cerrar aviso"
          @click="visible = null"
        >
          <BaseIcono nombre="cerrar" class="size-4" />
        </button>
      </div>
    </Transition>
  </div>
</template>
