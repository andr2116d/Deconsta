<script setup lang="ts">
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Categoria } from '../types'
import InsigniaCategoria from './InsigniaCategoria.vue'

defineProps<{ categoria: Categoria; ocupada: boolean }>()
const emit = defineEmits<{ editar: []; archivar: []; reactivar: [] }>()
</script>

<template>
  <li
    class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-borde py-4 last:border-b-0"
    :aria-labelledby="`categoria-${categoria.id}`"
  >
    <InsigniaCategoria
      :color="categoria.color"
      :icono="categoria.icono"
      :class="categoria.archivada ? 'opacity-60 grayscale' : ''"
    />
    <div class="min-w-0 flex-1">
      <h3
        :id="`categoria-${categoria.id}`"
        class="truncate text-[15px] font-extrabold"
        :class="categoria.archivada ? 'text-secundario' : ''"
      >
        {{ categoria.nombre }}
      </h3>
      <p class="text-[12px] text-secundario" :class="categoria.descripcion ? '' : 'italic'">
        {{ categoria.descripcion ?? 'Sin descripción' }}
      </p>
    </div>
    <div class="flex w-full justify-end gap-1 pl-14 sm:w-auto sm:pl-0">
      <BaseBoton
        v-if="categoria.archivada"
        variante="secundario"
        :cargando="ocupada"
        @click="emit('reactivar')"
      >
        Reactivar
        <span class="sr-only">{{ categoria.nombre }}</span>
      </BaseBoton>
      <template v-else>
        <BaseBoton variante="discreto" :deshabilitado="ocupada" @click="emit('editar')">
          <BaseIcono nombre="lapiz" class="size-4" />
          Editar
          <span class="sr-only">{{ categoria.nombre }}</span>
        </BaseBoton>
        <BaseBoton variante="discreto" :deshabilitado="ocupada" @click="emit('archivar')">
          <BaseIcono nombre="archivo" class="size-4" />
          Archivar
          <span class="sr-only">{{ categoria.nombre }}</span>
        </BaseBoton>
      </template>
    </div>
  </li>
</template>
