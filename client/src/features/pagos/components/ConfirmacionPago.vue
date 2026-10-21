<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import { formatearFecha } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Pago } from '../types'

/**
 * Cierre del registro del pago. A la asistente se le dice que su gerente lo verificará; al
 * gerente, que quedó confirmado y qué no se pudo comprobar.
 */
const props = defineProps<{ pago: Pago; rol: Rol }>()

const confirmado = computed(() => props.pago.estado === 'confirmado')
const avisos = computed(
  () => props.pago.comprobaciones?.filter((c) => c.resultado === 'aviso') ?? [],
)
</script>

<template>
  <section
    class="mx-auto max-w-[650px] animate-aparecer rounded-2xl border border-borde bg-white px-5 py-8 text-center sm:px-11 sm:py-11"
    aria-labelledby="titulo-seccion"
  >
    <span
      aria-hidden="true"
      class="mx-auto mb-5 grid size-16 place-items-center rounded-full"
      :class="confirmado ? 'bg-exito-fondo text-exito' : 'bg-acento-suave text-acento'"
    >
      <BaseIcono :nombre="confirmado ? 'check' : 'escudo'" class="size-[30px]" />
    </span>
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[25px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[29px]"
    >
      {{ confirmado ? 'Pago registrado y confirmado.' : 'Pago enviado a tu gerente.' }}
    </h1>
    <p class="mx-auto mt-3 max-w-[440px] text-[13px] text-secundario">
      {{
        confirmado
          ? 'La cuota quedó pagada. El comprobante queda guardado con el pago.'
          : 'Le llegó un aviso para verificarlo: revisará los comprobantes y lo confirmará. Mientras tanto, la cuota ya no figura por pagar.'
      }}
    </p>

    <dl
      class="my-6 grid grid-cols-1 gap-4 border-y border-dashed border-borde py-5 text-left sm:grid-cols-3"
    >
      <div>
        <dt class="text-[11px] text-secundario">Deuda</dt>
        <dd class="text-[14px] font-bold">{{ pago.concepto }}</dd>
        <dd v-if="pago.cuota > 1" class="text-[11px] text-secundario">Cuota {{ pago.cuota }}</dd>
      </div>
      <div>
        <dt class="text-[11px] text-secundario">Pagado</dt>
        <dd class="text-[14px] font-bold">{{ formatearSoles(pago.importe) }}</dd>
        <dd class="text-[11px] text-secundario">El {{ formatearFecha(pago.pagado_el) }}</dd>
      </div>
      <div>
        <dt class="text-[11px] text-secundario">Comprobantes</dt>
        <dd class="text-[14px] font-bold">{{ pago.comprobantes.length }}</dd>
        <dd v-if="Number(pago.comision) > 0" class="text-[11px] text-secundario">
          Comisión aparte: {{ formatearSoles(pago.comision) }}
        </dd>
      </div>
    </dl>

    <ul
      v-if="confirmado && avisos.length"
      class="mb-6 flex flex-col gap-1.5 rounded-[10px] bg-aviso-fondo p-4 text-left text-[12px] text-aviso"
    >
      <li v-for="aviso in avisos" :key="aviso.codigo" class="flex gap-2">
        <BaseIcono nombre="alerta" class="mt-0.5 size-3.5 shrink-0" />
        <span
          ><strong>{{ aviso.titulo }}:</strong> {{ aviso.detalle }}</span
        >
      </li>
    </ul>

    <div class="flex flex-col justify-center gap-2 sm:flex-row">
      <RouterLink
        :to="{ name: rol === 'asistente' ? 'pagos-por-completar' : 'calendario' }"
        class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[9px] bg-acento px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover"
      >
        {{ rol === 'asistente' ? 'Ver lo que falta pagar' : 'Volver al calendario' }}
      </RouterLink>
    </div>
  </section>
</template>
