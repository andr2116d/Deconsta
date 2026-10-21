<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import type { Categoria } from '@/features/categorias/types'
import { ESTADOS, TIPOS_DOCUMENTO } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { cercania, cuandoVence, partesDia } from '../fechas'
import type { Dia, Vencimiento } from '../types'

const props = defineProps<{
  dia: Dia
  hoy: Dia
  vencimientos: Vencimiento[]
  rol: Rol
  categoriaDe: (id: string | null) => Categoria | null
}>()

const encabezado = computed(() => partesDia(props.dia))
const total = computed(() => props.vencimientos.reduce((suma, v) => suma + Number(v.importe), 0))
const pasado = computed(() => cercania(props.dia, props.hoy) === 'pasado')

const TONOS = {
  pasado: 'text-secundario',
  hoy: 'bg-error-fondo text-error',
  pronto: 'bg-aviso-fondo text-aviso',
  despues: 'bg-acento-suave text-acento',
}

// Lo registrado por una asistente sin excepciones se paga ya, aunque al gerente le falte darle
// su visto bueno.
function estado(v: Vencimiento) {
  if (v.estado === 'registrada' && v.revision_pendiente) {
    return {
      texto: props.rol === 'gerente' ? 'Espera tu visto bueno' : 'En revisión del gerente',
      clase: 'bg-rosa text-ciruela',
    }
  }
  return ESTADOS[v.estado]
}

// Solo lo que espera la decisión del gerente tiene a dónde ir por ahora.
const decidible = (v: Vencimiento) =>
  props.rol === 'gerente' && (v.estado === 'por_autorizar' || v.revision_pendiente)
</script>

<template>
  <aside
    class="rounded-2xl border border-borde bg-white p-5 lg:sticky lg:top-[156px]"
    :aria-label="`Vencimientos del ${encabezado.fecha}`"
  >
    <p class="text-[12px] font-bold text-secundario">{{ encabezado.semana }}</p>
    <h2 class="text-[24px] leading-tight font-extrabold tracking-[-0.03em]">
      {{ encabezado.fecha }}
    </h2>
    <p class="mt-1 text-[13px] text-secundario">
      <template v-if="vencimientos.length">
        {{ vencimientos.length }} vencimiento{{ vencimientos.length === 1 ? '' : 's' }} ·
        <strong class="text-tinta">{{ formatearSoles(total) }}</strong>
      </template>
      <template v-else>Sin vencimientos</template>
    </p>

    <ul v-if="vencimientos.length" class="mt-5 flex flex-col gap-3">
      <li
        v-for="(v, i) in vencimientos"
        :key="`${v.deuda_id}-${v.cuota}`"
        class="animate-aparecer rounded-[12px] border border-borde p-3.5"
        :style="{ animationDelay: `${Math.min(i, 5) * 40}ms` }"
      >
        <div class="flex items-start gap-3">
          <InsigniaCategoria
            :color="categoriaDe(v.categoria_id)?.color ?? 'grafito'"
            :icono="categoriaDe(v.categoria_id)?.icono ?? 'etiqueta'"
            tamano="pequeno"
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <h3 class="text-[13px] leading-snug font-bold">{{ v.concepto }}</h3>
              <strong class="shrink-0 text-[13px] font-extrabold">
                {{ formatearSoles(v.importe) }}
              </strong>
            </div>
            <p class="mt-0.5 text-[11px] text-secundario">
              {{ categoriaDe(v.categoria_id)?.nombre ?? 'Otros' }} ·
              {{ TIPOS_DOCUMENTO[v.tipo_documento] }}
              <template v-if="v.cuotas > 1"> · cuota {{ v.cuota }} de {{ v.cuotas }}</template>
            </p>
            <p class="text-[11px] text-secundario">Registró {{ v.registrada_por }}</p>
            <div class="mt-2 flex flex-wrap items-center gap-1.5">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="TONOS[cercania(v.vence_el, hoy)]"
              >
                {{ cuandoVence(v.vence_el, hoy) }}
              </span>
              <span class="rounded-full px-2 py-0.5 text-[10px] font-bold" :class="estado(v).clase">
                {{ estado(v).texto }}
              </span>
            </div>
            <RouterLink
              v-if="decidible(v)"
              :to="{ name: 'por-autorizar', query: { deuda: v.deuda_id } }"
              class="mt-3 inline-flex items-center gap-1 text-[12px] font-bold text-acento hover:underline"
            >
              {{ v.estado === 'por_autorizar' ? 'Autorizar o rechazar' : 'Revisar' }}
              <BaseIcono nombre="derecha" class="size-3.5" />
            </RouterLink>
          </div>
        </div>
      </li>
    </ul>

    <div v-else class="mt-6 flex flex-col items-center py-8 text-center">
      <span
        aria-hidden="true"
        class="mb-3 grid size-12 place-items-center rounded-full bg-acento-suave text-acento"
      >
        <BaseIcono nombre="calendario" class="size-6" />
      </span>
      <h3 class="text-[16px] font-extrabold">Un día despejado.</h3>
      <p class="mt-1 text-[12px] text-secundario">
        {{ pasado ? 'Ese día no venció ninguna deuda.' : 'No vence ninguna deuda este día.' }}
      </p>
      <RouterLink
        v-if="!pasado"
        :to="{ name: 'registrar-deuda' }"
        class="mt-4 inline-flex items-center gap-1 text-[12px] font-bold text-acento hover:underline"
      >
        <BaseIcono nombre="mas" class="size-3.5" />
        Registrar una deuda
      </RouterLink>
    </div>
  </aside>
</template>
