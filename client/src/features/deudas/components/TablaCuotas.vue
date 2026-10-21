<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import { filtrarImporte, formatearSoles } from '@/features/reglas/importes'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { cuotasMensuales, MAXIMO_CUOTAS, sumarMeses, totalCuotas } from '../cuotas'
import type { CuotaNueva } from '../types'

/**
 * Cuotas de un préstamo o contrato. Se generan mensuales e iguales y luego se ajusta cada una:
 * la última suele ser distinta. El total solo orienta; el backend valida cada cuota.
 */
const props = defineProps<{ errores: Record<string, string> }>()
const cuotas = defineModel<CuotaNueva[]>({ required: true })

const id = useId()
const generador = ref({ cantidad: '12', importe: '', primera: cuotas.value[0]?.vence_el ?? '' })
const total = computed(() => totalCuotas(cuotas.value))
const error = (indice: number, campo: 'vence_el' | 'importe') =>
  props.errores[`cuotas.${indice}.${campo}`]

const CLASE_CONTROL =
  'min-h-[42px] w-full min-w-0 rounded-[7px] border bg-white px-2.5 text-[13px] transition-colors duration-200'

function generar() {
  const { cantidad, importe, primera } = generador.value
  cuotas.value = cuotasMensuales(Number(cantidad) || 1, filtrarImporte(importe), primera)
}

function agregar() {
  if (cuotas.value.length >= MAXIMO_CUOTAS) return
  const ultima = cuotas.value[cuotas.value.length - 1]
  cuotas.value = [
    ...cuotas.value,
    {
      vence_el: ultima?.vence_el ? sumarMeses(ultima.vence_el, 1) : '',
      importe: ultima?.importe ?? '',
    },
  ]
}

function quitar(indice: number) {
  if (cuotas.value.length > 1) cuotas.value = cuotas.value.filter((_, i) => i !== indice)
}

function cambiar(indice: number, campo: keyof CuotaNueva, valor: string) {
  cuotas.value = cuotas.value.map((c, i) =>
    i === indice ? { ...c, [campo]: campo === 'importe' ? filtrarImporte(valor) : valor } : c,
  )
}
</script>

<template>
  <div>
    <details class="group mb-4 rounded-[10px] border border-borde bg-fondo">
      <summary
        class="flex cursor-pointer list-none items-center gap-2 rounded-[10px] px-4 py-3 text-[13px] font-bold text-acento"
      >
        <BaseIcono nombre="mas" class="size-4 transition-transform group-open:rotate-45" />
        Generar cuotas mensuales iguales
      </summary>
      <div class="grid gap-3 px-4 pb-4 sm:grid-cols-[90px_1fr_1fr_auto] sm:items-end">
        <label class="flex flex-col gap-1 text-[12px] font-bold">
          Cuotas
          <input
            v-model="generador.cantidad"
            inputmode="numeric"
            :class="[CLASE_CONTROL, 'border-control']"
            @input="generador.cantidad = generador.cantidad.replace(/\D/g, '').slice(0, 3)"
          />
        </label>
        <label class="flex flex-col gap-1 text-[12px] font-bold">
          Importe de cada una (S/)
          <input
            :value="generador.importe"
            inputmode="decimal"
            placeholder="0.00"
            :class="[CLASE_CONTROL, 'border-control']"
            @input="generador.importe = filtrarImporte(($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="flex flex-col gap-1 text-[12px] font-bold">
          Primer vencimiento
          <input
            v-model="generador.primera"
            type="date"
            :class="[CLASE_CONTROL, 'border-control']"
          />
        </label>
        <BaseBoton variante="secundario" @click="generar">Generar</BaseBoton>
      </div>
    </details>

    <table
      class="w-full border-separate border-spacing-y-1.5 text-left"
      :aria-describedby="`${id}-total`"
    >
      <caption class="sr-only">
        Cuotas de la deuda
      </caption>
      <thead class="text-[11px] text-secundario">
        <tr>
          <th scope="col" class="w-10 font-bold">N.°</th>
          <th scope="col" class="font-bold">Vence el</th>
          <th scope="col" class="font-bold">Importe (S/)</th>
          <th scope="col"><span class="sr-only">Quitar</span></th>
        </tr>
      </thead>
      <TransitionGroup tag="tbody" name="vista">
        <tr v-for="(cuota, indice) in cuotas" :key="indice" class="align-top">
          <td class="pt-3 text-[12px] font-bold text-secundario">{{ indice + 1 }}</td>
          <td class="pr-2">
            <input
              type="date"
              :value="cuota.vence_el"
              :aria-label="`Vencimiento de la cuota ${indice + 1}`"
              :aria-invalid="error(indice, 'vence_el') ? 'true' : undefined"
              :class="[
                CLASE_CONTROL,
                error(indice, 'vence_el') ? 'border-error' : 'border-control',
              ]"
              @input="cambiar(indice, 'vence_el', ($event.target as HTMLInputElement).value)"
            />
            <p v-if="error(indice, 'vence_el')" class="mt-1 text-[11px] text-error">
              {{ error(indice, 'vence_el') }}
            </p>
          </td>
          <td class="pr-2">
            <input
              :value="cuota.importe"
              inputmode="decimal"
              placeholder="0.00"
              :aria-label="`Importe de la cuota ${indice + 1}`"
              :aria-invalid="error(indice, 'importe') ? 'true' : undefined"
              :class="[CLASE_CONTROL, error(indice, 'importe') ? 'border-error' : 'border-control']"
              @input="cambiar(indice, 'importe', ($event.target as HTMLInputElement).value)"
            />
            <p v-if="error(indice, 'importe')" class="mt-1 text-[11px] text-error">
              {{ error(indice, 'importe') }}
            </p>
          </td>
          <td class="w-10">
            <button
              type="button"
              class="grid size-[42px] place-items-center rounded-lg text-secundario hover:bg-error-fondo hover:text-error disabled:opacity-40"
              :disabled="cuotas.length === 1"
              :aria-label="`Quitar la cuota ${indice + 1}`"
              @click="quitar(indice)"
            >
              <BaseIcono nombre="cerrar" class="size-4" />
            </button>
          </td>
        </tr>
      </TransitionGroup>
    </table>

    <div class="mt-2 flex flex-wrap items-center justify-between gap-3">
      <BaseBoton
        variante="discreto"
        :deshabilitado="cuotas.length >= MAXIMO_CUOTAS"
        @click="agregar"
      >
        <BaseIcono nombre="mas" class="size-4" />
        Agregar cuota
      </BaseBoton>
      <p :id="`${id}-total`" class="text-[13px]" aria-live="polite">
        {{ cuotas.length }} {{ cuotas.length === 1 ? 'cuota' : 'cuotas' }} ·
        <strong>{{ total ? formatearSoles(total) : 'Completa los importes' }}</strong>
      </p>
    </div>
    <p v-if="errores.cuotas" class="mt-1 text-[12px] text-error">{{ errores.cuotas }}</p>
  </div>
</template>
