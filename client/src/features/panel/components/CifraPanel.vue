<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import { RouterLink } from 'vue-router'

import BaseIcono from '@/shared/components/BaseIcono.vue'

/** Una cifra del panel; con destino, lleva a donde se atiende. */
defineProps<{
  etiqueta: string
  valor: string
  detalle?: string
  destino?: RouteLocationRaw
  /** Resalta la cifra cuando pide atención. */
  atencion?: boolean
}>()
</script>

<template>
  <component
    :is="destino ? RouterLink : 'div'"
    :to="destino"
    class="group flex min-h-[96px] flex-col justify-between gap-2 rounded-[14px] border bg-white p-4 transition-[border-color,box-shadow] duration-200"
    :class="[
      atencion ? 'border-aviso/60' : 'border-borde',
      destino ? 'hover:border-acento hover:shadow-[0_8px_26px_#30233012]' : '',
    ]"
  >
    <span class="flex items-center justify-between text-[12px] font-bold text-secundario">
      {{ etiqueta }}
      <BaseIcono
        v-if="destino"
        nombre="derecha"
        class="size-4 text-acento transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
      />
    </span>
    <span>
      <strong class="block text-[24px] leading-none font-extrabold tracking-[-0.03em]">
        {{ valor }}
      </strong>
      <small v-if="detalle" class="mt-1 block text-[11px] text-secundario">{{ detalle }}</small>
    </span>
  </component>
</template>
