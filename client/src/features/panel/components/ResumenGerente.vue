<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { RouterLink } from 'vue-router'

import { cuandoVence } from '@/features/calendario/fechas'
import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import type { Categoria } from '@/features/categorias/types'
import AccionPedido from '@/features/pagos/components/AccionPedido.vue'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import type { Pendiente, Resumen, TipoPendiente } from '../types'
import CifraPanel from './CifraPanel.vue'

/** El resumen del gerente: cifras del espacio, su bandeja de decisiones y los próximos pagos. */
const props = defineProps<{
  resumen: Resumen
  hoy: string
  categoriaDe: (id: string | null) => Categoria | undefined
}>()
const emit = defineEmits<{ cambio: [] }>()

const TIPOS: Record<TipoPendiente, { texto: string; icono: NombreIcono }> = {
  autorizar_deuda: { texto: 'Autorizar deuda', icono: 'escudo' },
  revisar_deuda: { texto: 'Dar visto bueno', icono: 'documento' },
  verificar_pago: { texto: 'Verificar pago', icono: 'check' },
  aprobar_mora: { texto: 'Aprobar mora', icono: 'alerta' },
}

function destino(p: Pendiente): RouteLocationRaw {
  if (p.tipo === 'verificar_pago') return { name: 'por-verificar', query: { pago: p.id } }
  if (p.tipo === 'aprobar_mora') return { name: 'por-verificar' }
  return { name: 'por-autorizar', query: { deuda: p.deuda_id } }
}

const deudas = computed(
  () =>
    props.resumen.pendientes.filter(
      (p) => p.tipo === 'autorizar_deuda' || p.tipo === 'revisar_deuda',
    ).length,
)
const pagos = computed(() => props.resumen.pendientes.length - deudas.value)
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <CifraPanel
        etiqueta="Por pagar"
        :valor="formatearSoles(resumen.por_pagar)"
        :detalle="`${resumen.cuotas_por_pagar} cuotas${resumen.vencidas ? ` · ${resumen.vencidas} vencidas` : ''}`"
        :destino="{ name: 'pagos-por-completar' }"
        :atencion="resumen.vencidas > 0"
      />
      <CifraPanel
        etiqueta="Esperan autorización"
        :valor="String(deudas)"
        :detalle="deudas === 1 ? 'deuda' : 'deudas'"
        :destino="{ name: 'por-autorizar' }"
        :atencion="deudas > 0"
      />
      <CifraPanel
        etiqueta="Esperan tu revisión"
        :valor="String(pagos)"
        detalle="pagos y moras"
        :destino="{ name: 'por-verificar' }"
        :atencion="pagos > 0"
      />
      <CifraPanel
        etiqueta="Pagado este mes"
        :valor="formatearSoles(resumen.pagado_mes)"
        :detalle="`${resumen.pagos_mes} ${resumen.pagos_mes === 1 ? 'pago' : 'pagos'}`"
      />
    </div>

    <section aria-labelledby="titulo-bandeja">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-bandeja" class="text-[17px] font-extrabold">
          {{ resumen.pendientes.length ? 'Tu bandeja de decisiones' : 'Tu espacio está al día' }}
        </h2>
        <span class="text-[12px] text-secundario">
          {{ resumen.pendientes.length }}
          {{ resumen.pendientes.length === 1 ? 'pendiente' : 'pendientes' }} · lo que vence antes,
          primero
        </span>
      </div>
      <ul v-if="resumen.pendientes.length" class="flex flex-col gap-2">
        <li
          v-for="(p, i) in resumen.pendientes"
          :key="`${p.tipo}-${p.id}`"
          class="animate-aparecer"
          :style="{ animationDelay: `${Math.min(i, 6) * 40}ms` }"
        >
          <RouterLink
            :to="destino(p)"
            class="flex items-center gap-3 rounded-[12px] border border-borde bg-white px-4 py-3 transition-[border-color,box-shadow] duration-200 hover:border-acento hover:shadow-[0_8px_26px_#30233012]"
          >
            <span
              aria-hidden="true"
              class="grid size-9 shrink-0 place-items-center rounded-[10px] bg-acento-suave text-acento"
            >
              <BaseIcono :nombre="TIPOS[p.tipo].icono" class="size-4" />
            </span>
            <span class="min-w-0 flex-1">
              <strong class="block truncate text-[13px]">{{ p.concepto }}</strong>
              <small class="text-[11px] text-secundario">
                {{ TIPOS[p.tipo].texto }} · de {{ p.por }} ·
                {{ cuandoVence(p.vence_el, hoy) }}
              </small>
            </span>
            <strong class="shrink-0 text-[14px]">{{ formatearSoles(p.importe) }}</strong>
            <BaseIcono nombre="derecha" class="size-4 shrink-0 text-acento" />
          </RouterLink>
        </li>
      </ul>
      <p
        v-else
        class="rounded-[12px] border border-dashed border-borde bg-white px-4 py-6 text-center text-[13px] text-secundario"
      >
        Nada espera tu decisión. Lo que registren o paguen tus asistentes aparecerá aquí.
      </p>
    </section>

    <section aria-labelledby="titulo-proximos">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="titulo-proximos" class="text-[17px] font-extrabold">Próximos pagos</h2>
        <RouterLink
          :to="{ name: 'pagos-por-completar' }"
          class="inline-flex items-center gap-1 text-[12px] font-bold text-acento hover:underline"
        >
          Ver todo lo que falta pagar
          <BaseIcono nombre="derecha" class="size-3.5" />
        </RouterLink>
      </div>
      <ul v-if="resumen.proximas.length" class="grid gap-2 sm:grid-cols-2">
        <li
          v-for="c in resumen.proximas"
          :key="`${c.deuda_id}-${c.cuota}`"
          class="flex items-start gap-3 rounded-[12px] border border-borde bg-white p-3.5"
        >
          <InsigniaCategoria
            :icono="categoriaDe(c.categoria_id)?.icono ?? 'etiqueta'"
            :color="categoriaDe(c.categoria_id)?.color ?? 'ciruela'"
            tamano="pequeno"
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <strong class="truncate text-[13px]">{{ c.concepto }}</strong>
              <strong class="shrink-0 text-[13px]">{{ formatearSoles(c.importe) }}</strong>
            </div>
            <p
              class="mb-2 text-[11px]"
              :class="c.vence_el < hoy ? 'font-bold text-error' : 'text-secundario'"
            >
              {{ cuandoVence(c.vence_el, hoy) }}
              <template v-if="c.cuotas > 1"> · cuota {{ c.cuota }} de {{ c.cuotas }}</template>
            </p>
            <AccionPedido
              :deuda-id="c.deuda_id"
              :cuota="c.cuota"
              :concepto="c.concepto"
              :importe="c.importe"
              :vence-el="c.vence_el"
              :pedido="c.pedido"
              @cambio="emit('cambio')"
            />
          </div>
        </li>
      </ul>
      <p
        v-else
        class="rounded-[12px] border border-dashed border-borde bg-white px-4 py-6 text-center text-[13px] text-secundario"
      >
        No falta pagar ninguna cuota.
      </p>
    </section>
  </div>
</template>
