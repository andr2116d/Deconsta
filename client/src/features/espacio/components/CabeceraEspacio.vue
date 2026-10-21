<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Usuario } from '@/features/acceso/types'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import MarcaDeconsta from '@/shared/components/MarcaDeconsta.vue'

import MenuCuenta from './MenuCuenta.vue'
import PestanasEspacio from './PestanasEspacio.vue'

const props = defineProps<{ usuario: Usuario; contrasenaTemporal: boolean; saliendo: boolean }>()
const emit = defineEmits<{ 'cambiar-contrasena': []; salir: [] }>()

const espacio = computed(() =>
  props.usuario.rol === 'gerente'
    ? { lugar: 'Tu espacio de dirección', tarea: 'Control de deudas' }
    : { lugar: 'Tu espacio de asistencia', tarea: 'Registro y ejecución' },
)
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-borde bg-white">
    <div class="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10 min-[1920px]:max-w-[1680px]">
      <div class="flex h-16 items-center gap-3 lg:h-[76px] lg:gap-6">
        <RouterLink
          :to="{ name: 'inicio' }"
          aria-label="Deconsta, ir al inicio"
          class="shrink-0 rounded-md max-[359px]:[&>span]:text-[22px]"
        >
          <MarcaDeconsta />
        </RouterLink>
        <p
          class="hidden border-l border-borde pl-6 text-[11px] leading-snug text-secundario lg:block"
        >
          {{ espacio.lugar }}
          <strong class="block text-[13px] text-tinta">{{ espacio.tarea }}</strong>
        </p>

        <div class="ml-auto flex items-center gap-1 sm:gap-2">
          <RouterLink
            :to="{ name: 'registrar-deuda' }"
            class="inline-flex size-11 items-center justify-center gap-2 rounded-[9px] bg-acento text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover sm:w-auto sm:px-4"
          >
            <BaseIcono nombre="mas" class="size-[18px]" />
            <span class="sr-only sm:not-sr-only">Registrar deuda</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'notificaciones' }"
            aria-label="Notificaciones"
            class="grid size-11 place-items-center rounded-[9px] text-tinta transition-colors duration-200 hover:bg-acento-suave hover:text-acento"
            exact-active-class="bg-acento-suave !text-acento"
          >
            <BaseIcono nombre="avisos" class="size-5" />
          </RouterLink>
          <MenuCuenta
            :usuario="usuario"
            :contrasena-temporal="contrasenaTemporal"
            :saliendo="saliendo"
            @cambiar-contrasena="emit('cambiar-contrasena')"
            @salir="emit('salir')"
          />
        </div>
      </div>

      <PestanasEspacio :rol="usuario.rol" />
    </div>
  </header>
</template>
