<script setup lang="ts">
import { COLORES } from '@/features/categorias/catalogo'
import type { ColorCategoria } from '@/features/categorias/types'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { cercania, cuandoVence } from '../fechas'
import type { Dia, Vencimiento } from '../types'

defineProps<{
  dias: number
  hoy: Dia
  vencimientos: Vencimiento[]
  colorDe: (categoriaId: string | null) => ColorCategoria
}>()

const emit = defineEmits<{ seleccionar: [dia: Dia] }>()

const TONOS = {
  pasado: 'text-secundario',
  hoy: 'text-error',
  pronto: 'text-aviso',
  despues: 'text-secundario',
}
</script>

<template>
  <section aria-labelledby="titulo-proximos">
    <h2 id="titulo-proximos" class="mb-2 text-[12px] font-bold text-secundario">
      Lo que vence en los próximos {{ dias }} días
    </h2>
    <p
      v-if="!vencimientos.length"
      class="rounded-[12px] border border-dashed border-borde bg-white px-4 py-3 text-[13px] text-secundario"
    >
      Nada vence en los próximos {{ dias }} días.
    </p>
    <ul v-else class="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1">
      <li
        v-for="v in vencimientos"
        :key="`${v.deuda_id}-${v.cuota}`"
        class="w-[220px] shrink-0 snap-start"
      >
        <button
          type="button"
          class="flex h-full w-full flex-col gap-1 rounded-[12px] border border-borde bg-white p-3 text-left transition-[border-color,box-shadow] duration-200 hover:border-control hover:shadow-[0_8px_26px_#30233012]"
          @click="emit('seleccionar', v.vence_el)"
        >
          <span
            class="flex items-center gap-1.5 text-[11px] font-bold"
            :class="TONOS[cercania(v.vence_el, hoy)]"
          >
            <BaseIcono
              :nombre="cercania(v.vence_el, hoy) === 'despues' ? 'calendario' : 'reloj'"
              class="size-3.5"
            />
            {{ cuandoVence(v.vence_el, hoy) }}
          </span>
          <span class="flex items-center gap-1.5">
            <i
              aria-hidden="true"
              class="size-2 shrink-0 rounded-full"
              :style="{ backgroundColor: COLORES[colorDe(v.categoria_id)].tinta }"
            />
            <strong class="truncate text-[13px]">{{ v.concepto }}</strong>
          </span>
          <span class="text-[13px] font-extrabold">{{ formatearSoles(v.importe) }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>
