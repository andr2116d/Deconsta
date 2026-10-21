<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { cuandoVence } from '@/features/calendario/fechas'
import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import type { Categoria } from '@/features/categorias/types'
import { formatearFecha, nombresLugares } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { CuotaPorPagar } from '../types'

/** Una cuota que falta pagar: cuánto, cuándo vence, dónde se paga y el paso para registrarla. */
const props = defineProps<{
  cuota: CuotaPorPagar
  hoy: string
  categoria?: Categoria
  bloqueado?: boolean
}>()

const vencida = computed(() => props.cuota.vencida_hace !== null)
const cuando = computed(() => cuandoVence(props.cuota.vence_el, props.hoy))
</script>

<template>
  <article
    class="flex flex-col gap-3 rounded-[14px] border bg-white p-4 transition-[border-color,box-shadow] duration-200 hover:shadow-[0_8px_26px_#30233012] sm:flex-row sm:items-center"
    :class="vencida ? 'border-error/40' : 'border-borde'"
  >
    <div class="flex min-w-0 flex-1 items-start gap-3">
      <InsigniaCategoria
        :icono="categoria?.icono ?? 'etiqueta'"
        :color="categoria?.color ?? 'ciruela'"
      />
      <div class="min-w-0 flex-1">
        <h3 class="truncate text-[14px] font-extrabold">{{ cuota.concepto }}</h3>
        <p class="mt-0.5 text-[11px] text-secundario">
          {{ categoria?.nombre ?? 'Otros' }}
          <template v-if="cuota.cuotas > 1">
            · cuota {{ cuota.cuota }} de {{ cuota.cuotas }}</template
          >
          <template v-if="cuota.codigo_pago"> · código {{ cuota.codigo_pago }}</template>
        </p>
        <p class="mt-0.5 text-[11px] text-secundario">
          Se paga en: {{ nombresLugares(cuota.lugares_pago) }}
        </p>
        <p v-if="cuota.devuelto_por" class="mt-1.5 text-[12px] text-error">
          Tu gerente devolvió el pago: {{ cuota.devuelto_por }}
        </p>
        <span
          class="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold"
          :class="vencida ? 'bg-error-fondo text-error' : 'bg-fondo text-secundario'"
        >
          <BaseIcono :nombre="vencida ? 'alerta' : 'calendario'" class="size-3.5" />
          {{ cuando }} · {{ formatearFecha(cuota.vence_el) }}
        </span>
      </div>
    </div>
    <div class="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
      <strong class="text-[18px] font-extrabold tracking-[-0.02em]">
        {{ formatearSoles(cuota.importe) }}
      </strong>
      <span
        v-if="bloqueado"
        class="text-[12px] font-bold text-secundario"
        title="Tu registro de pagos está en pausa"
      >
        En pausa
      </span>
      <RouterLink
        v-else
        :to="{ name: 'registrar-pago', query: { deuda: cuota.deuda_id, cuota: cuota.cuota } }"
        class="inline-flex min-h-10 items-center gap-1.5 rounded-[9px] bg-acento px-3.5 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover"
        :aria-label="`Registrar el pago de ${cuota.concepto}`"
      >
        Registrar pago
        <BaseIcono nombre="derecha" class="size-4" />
      </RouterLink>
    </div>
  </article>
</template>
