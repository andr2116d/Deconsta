<script setup lang="ts">
import { computed } from 'vue'

import BaseIcono from '@/shared/components/BaseIcono.vue'

import { COLORES } from '../catalogo'
import type { ColorCategoria, IconoCategoria } from '../types'

// Decorativa: el nombre de la categoría la acompaña siempre.
const props = withDefaults(
  defineProps<{
    color: ColorCategoria
    icono: IconoCategoria
    tamano?: 'pequeno' | 'normal' | 'grande'
  }>(),
  { tamano: 'normal' },
)

const TAMANOS = {
  pequeno: { caja: 'size-9 rounded-full', icono: 'size-4' },
  normal: { caja: 'size-10 rounded-xl', icono: 'size-5' },
  grande: { caja: 'size-12 rounded-[14px]', icono: 'size-6' },
}

const tono = computed(() => COLORES[props.color])
</script>

<template>
  <span
    aria-hidden="true"
    class="grid shrink-0 place-items-center transition-colors duration-200"
    :class="TAMANOS[tamano].caja"
    :style="{ backgroundColor: tono.fondo, color: tono.tinta }"
  >
    <BaseIcono :nombre="icono" :class="TAMANOS[tamano].icono" />
  </span>
</template>
