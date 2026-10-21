<script setup lang="ts">
import { computed } from 'vue'

import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import type { Categoria } from '@/features/categorias/types'
import { ESTADOS, formatearFecha, MOTIVOS, nombresLugares } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { ACCIONES, formatearMomento, MORAS, PAGOS } from '../catalogo'
import type { CuotaHistorial, DeudaHistorial } from '../types'

/**
 * Una deuda del historial: su estado, el de cada cuota y lo que pasó con ella. Al gerente se le
 * resalta lo que espera su decisión.
 */
const props = defineProps<{
  deuda: DeudaHistorial
  hoy: string
  gerente: boolean
  categoria?: Categoria
}>()

const pendientes = computed(() => {
  const d = props.deuda
  const lista: string[] = []
  if (d.estado === 'por_autorizar') lista.push('Espera autorización')
  if (d.revision_pendiente) lista.push('Espera visto bueno')
  if (d.pagos.some((p) => p.estado === 'por_verificar')) lista.push('Pago por verificar')
  if (d.moras.some((m) => m.estado === 'por_aprobar')) lista.push('Mora por aprobar')
  return lista
})
const superaLimite = computed(() => props.deuda.motivos.includes('IMPORTE_SOBRE_LIMITE'))
const resaltada = computed(() => props.gerente && pendientes.value.length > 0)
const sePaga = computed(() => props.deuda.estado === 'registrada')

function estadoCuota(c: CuotaHistorial) {
  if (c.pago) return PAGOS[c.pago]
  if (!sePaga.value) return { texto: 'No se paga', clase: 'bg-fondo text-secundario' }
  if (c.vence_el < props.hoy) return { texto: 'Vencida', clase: 'bg-error-fondo text-error' }
  return { texto: 'Por pagar', clase: 'bg-fondo text-secundario' }
}

const confianzaDe = (numero: number) =>
  props.deuda.pagos.find((p) => p.cuota === numero && p.estado !== 'devuelto')?.confianza
</script>

<template>
  <article
    class="rounded-[14px] border bg-white p-4 transition-shadow duration-200 hover:shadow-[0_8px_26px_#30233012] sm:p-5"
    :class="resaltada ? 'border-aviso/60 bg-aviso-fondo/30' : 'border-borde'"
  >
    <div class="flex items-start gap-3">
      <InsigniaCategoria
        :icono="categoria?.icono ?? 'etiqueta'"
        :color="categoria?.color ?? 'ciruela'"
      />
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <h3 class="min-w-0 text-[15px] leading-snug font-extrabold">{{ deuda.concepto }}</h3>
          <strong class="text-[16px] font-extrabold tracking-[-0.02em]">
            {{ formatearSoles(deuda.importe) }}
          </strong>
        </div>
        <p class="mt-0.5 text-[11px] text-secundario">
          {{ categoria?.nombre ?? 'Otros' }} · registró {{ deuda.registrada_por }} el
          {{ formatearMomento(deuda.creado_en) }} · {{ nombresLugares(deuda.lugares_pago) }}
        </p>
        <div class="mt-2 flex flex-wrap items-center gap-1.5">
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="ESTADOS[deuda.estado].clase"
          >
            {{ ESTADOS[deuda.estado].texto }}
          </span>
          <span
            v-for="p in pendientes.filter((t) => t !== 'Espera autorización')"
            :key="p"
            class="rounded-full bg-aviso-fondo px-2 py-0.5 text-[10px] font-bold text-aviso"
          >
            {{ p }}
          </span>
          <span
            v-if="superaLimite"
            class="rounded-full bg-error-fondo px-2 py-0.5 text-[10px] font-bold text-error"
          >
            {{ MOTIVOS.IMPORTE_SOBRE_LIMITE }}
          </span>
        </div>
        <p v-if="deuda.motivo_decision" class="mt-2 text-[12px] text-secundario">
          Motivo: {{ deuda.motivo_decision }}
        </p>
      </div>
    </div>

    <ul class="mt-4 flex flex-col divide-y divide-borde rounded-[10px] border border-borde">
      <li
        v-for="c in deuda.cuotas"
        :key="c.numero"
        class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2 text-[12px]"
      >
        <span>
          <template v-if="deuda.cuotas.length > 1">Cuota {{ c.numero }} · </template>
          vence el {{ formatearFecha(c.vence_el) }}
        </span>
        <span class="flex flex-wrap items-center gap-1.5">
          <span
            v-if="c.mora"
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="MORAS[c.mora].clase"
          >
            {{ MORAS[c.mora].texto }}
          </span>
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="estadoCuota(c).clase"
          >
            {{ estadoCuota(c).texto }}
          </span>
          <span
            v-if="gerente && confianzaDe(c.numero) != null"
            class="text-[11px] text-secundario"
            title="Cuánto respaldan los comprobantes el pago"
          >
            {{ confianzaDe(c.numero) }} %
          </span>
          <strong>{{ formatearSoles(c.importe) }}</strong>
        </span>
      </li>
    </ul>

    <details class="group mt-3">
      <summary
        class="inline-flex min-h-9 cursor-pointer list-none items-center gap-1 text-[12px] font-bold text-acento hover:underline"
      >
        <BaseIcono
          nombre="abajo"
          class="size-3.5 transition-transform group-open:rotate-180 motion-reduce:transition-none"
        />
        Lo que pasó · {{ deuda.eventos.length }}
      </summary>
      <ol class="mt-2 flex flex-col gap-2.5 border-l border-borde pl-4">
        <li v-for="(e, i) in deuda.eventos" :key="i" class="relative text-[12px]">
          <span
            aria-hidden="true"
            class="absolute top-0.5 -left-[25px] grid size-[17px] place-items-center rounded-full border border-borde bg-white text-secundario"
          >
            <BaseIcono :nombre="ACCIONES[e.accion].icono" class="size-2.5" />
          </span>
          <p>
            <strong>{{ e.actor ?? 'Una cuenta eliminada' }}</strong>
            {{ ACCIONES[e.accion].texto }}
            <template v-if="e.cuota && deuda.cuotas.length > 1"> (cuota {{ e.cuota }})</template>
          </p>
          <p class="text-[11px] text-secundario">{{ formatearMomento(e.en) }}</p>
          <p v-if="e.motivo" class="mt-0.5 text-[11px] text-secundario">«{{ e.motivo }}»</p>
        </li>
      </ol>
    </details>
  </article>
</template>
