<script setup lang="ts">
import { nextTick, ref } from 'vue'

import { COLORES } from '@/features/categorias/catalogo'
import type { ColorCategoria } from '@/features/categorias/types'
import { formatearSoles } from '@/features/reglas/importes'

import { cercania, fechaLarga, mesDe, nombreMes, numeroDia, sumarDias } from '../fechas'
import type { Dia, Mes, Vencimiento } from '../types'

const props = defineProps<{
  semanas: Dia[][]
  mes: Mes
  hoy: Dia
  seleccionado: Dia
  porDia: Map<Dia, Vencimiento[]>
  colorDe: (categoriaId: string | null) => ColorCategoria
}>()

const emit = defineEmits<{ seleccionar: [dia: Dia] }>()

const DIAS_SEMANA = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const VISIBLES = 2

const cuadricula = ref<HTMLElement | null>(null)

const de = (dia: Dia) => props.porDia.get(dia) ?? []
const total = (dia: Dia) => de(dia).reduce((suma, v) => suma + Number(v.importe), 0)

function etiqueta(dia: Dia) {
  const lista = de(dia)
  const cuantos = lista.length
    ? `${lista.length} vencimiento${lista.length === 1 ? '' : 's'}, ${formatearSoles(total(dia))}`
    : 'sin vencimientos'
  return `${fechaLarga(dia)}${dia === props.hoy ? ' (hoy)' : ''}: ${cuantos}`
}

// Un día con vencimientos lleva el tono de su cercanía; el color nunca va solo: el panel del día
// dice con palabras cuándo vence.
function tonoDia(dia: Dia) {
  if (!de(dia).length) return ''
  return {
    pasado: 'before:bg-control/50',
    hoy: 'before:bg-error',
    pronto: 'before:bg-aviso',
    despues: 'before:bg-acento/60',
  }[cercania(dia, props.hoy)]
}

// Cuadrícula con un solo día enfocable: las flechas recorren los días, Inicio y Fin la semana.
// Pasar de mes lo resuelve la vista al recibir un día de otro mes.
const SALTOS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }

async function mover(evento: KeyboardEvent, dia: Dia) {
  const semana = (new Date(`${dia}T00:00:00Z`).getUTCDay() + 6) % 7
  const salto =
    SALTOS[evento.key] ??
    (evento.key === 'Home' ? -semana : evento.key === 'End' ? 6 - semana : null)
  if (salto === null) return
  evento.preventDefault()
  emit('seleccionar', sumarDias(dia, salto))
  await nextTick()
  cuadricula.value?.querySelector<HTMLElement>('[tabindex="0"]')?.focus()
}
</script>

<template>
  <div
    ref="cuadricula"
    role="grid"
    :aria-label="`Vencimientos de ${nombreMes(mes)}`"
    class="select-none"
  >
    <div role="row" class="grid grid-cols-7 border-b border-borde">
      <span
        v-for="nombre in DIAS_SEMANA"
        :key="nombre"
        role="columnheader"
        class="py-2 text-center text-[11px] font-bold tracking-wide text-secundario uppercase"
      >
        {{ nombre }}
      </span>
    </div>
    <div
      v-for="semana in semanas"
      :key="semana[0]"
      role="row"
      class="grid grid-cols-7 border-b border-borde last:border-b-0"
    >
      <div
        v-for="dia in semana"
        :key="dia"
        role="gridcell"
        :aria-selected="dia === seleccionado"
        class="border-r border-borde last:border-r-0"
      >
        <button
          type="button"
          :data-dia="dia"
          :tabindex="dia === seleccionado ? 0 : -1"
          :aria-label="etiqueta(dia)"
          :aria-current="dia === hoy ? 'date' : undefined"
          class="relative flex h-full min-h-14 w-full flex-col gap-1 p-1.5 text-left transition-colors duration-200 before:absolute before:inset-x-1.5 before:top-0 before:h-[3px] before:rounded-b-full before:content-[''] focus-visible:-outline-offset-2 sm:min-h-[104px] sm:p-2"
          :class="[
            tonoDia(dia),
            mesDe(dia) === mes ? 'bg-white hover:bg-rosa-suave' : 'bg-fondo text-control',
            dia === seleccionado ? 'z-10 ring-2 ring-acento ring-inset' : '',
          ]"
          @click="emit('seleccionar', dia)"
          @keydown="mover($event, dia)"
        >
          <span class="flex items-center justify-between gap-1">
            <span
              class="grid size-6 place-items-center rounded-full text-[12px] font-bold"
              :class="dia === hoy ? 'bg-acento text-white' : ''"
            >
              {{ numeroDia(dia) }}
            </span>
            <small
              v-if="de(dia).length"
              aria-hidden="true"
              class="hidden truncate text-[10px] font-bold text-secundario lg:block"
            >
              {{ formatearSoles(total(dia)) }}
            </small>
          </span>

          <!-- En pantallas chicas solo caben puntos; el panel del día da el detalle. -->
          <span v-if="de(dia).length" aria-hidden="true" class="flex flex-wrap gap-1 sm:hidden">
            <i
              v-for="v in de(dia).slice(0, 4)"
              :key="`${v.deuda_id}-${v.cuota}`"
              class="size-1.5 rounded-full"
              :style="{ backgroundColor: COLORES[colorDe(v.categoria_id)].tinta }"
            />
          </span>
          <span aria-hidden="true" class="hidden flex-col gap-1 sm:flex">
            <span
              v-for="v in de(dia).slice(0, VISIBLES)"
              :key="`${v.deuda_id}-${v.cuota}`"
              class="flex items-center gap-1.5 truncate rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-tinta"
              :class="[
                v.estado === 'por_autorizar' ? 'outline-1 outline-aviso outline-dashed' : '',
                cercania(dia, hoy) === 'pasado' ? 'opacity-60' : '',
              ]"
              :style="{ backgroundColor: COLORES[colorDe(v.categoria_id)].fondo }"
            >
              <i
                class="size-1.5 shrink-0 rounded-full"
                :style="{ backgroundColor: COLORES[colorDe(v.categoria_id)].tinta }"
              />
              <span class="truncate">{{ v.concepto }}</span>
            </span>
            <small
              v-if="de(dia).length > VISIBLES"
              class="px-1.5 text-[10px] font-bold text-secundario"
            >
              +{{ de(dia).length - VISIBLES }} más
            </small>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
