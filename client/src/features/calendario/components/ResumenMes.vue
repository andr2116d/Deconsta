<script setup lang="ts">
import { computed } from 'vue'

import { formatearSoles } from '@/features/reglas/importes'

import { mesDe } from '../fechas'
import type { Dia, Mes, Vencimiento } from '../types'

const props = defineProps<{ mes: Mes; hoy: Dia; vencimientos: Vencimiento[] }>()

const delMes = computed(() => props.vencimientos.filter((v) => mesDe(v.vence_el) === props.mes))
const suma = (lista: Vencimiento[]) => lista.reduce((total, v) => total + Number(v.importe), 0)
const vencidos = computed(() => delMes.value.filter((v) => v.vence_el < props.hoy))
const porVencer = computed(() => delMes.value.filter((v) => v.vence_el >= props.hoy))
const porAutorizar = computed(() => delMes.value.filter((v) => v.estado === 'por_autorizar'))

const plural = (n: number, palabra: string) => `${n} ${palabra}${n === 1 ? '' : 's'}`

const datos = computed(() => [
  {
    titulo: 'Vence en el mes',
    valor: formatearSoles(suma(delMes.value)),
    detalle: plural(delMes.value.length, 'vencimiento'),
  },
  {
    titulo: 'Desde hoy',
    valor: formatearSoles(suma(porVencer.value)),
    detalle: plural(porVencer.value.length, 'vencimiento'),
  },
  {
    titulo: 'Fechas ya pasadas',
    valor: formatearSoles(suma(vencidos.value)),
    detalle: plural(vencidos.value.length, 'vencimiento'),
  },
  {
    titulo: 'Esperan autorización',
    valor: String(porAutorizar.value.length),
    detalle: 'no se pagan hasta decidir',
  },
])
</script>

<template>
  <dl
    class="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-borde bg-borde sm:grid-cols-4"
  >
    <div v-for="dato in datos" :key="dato.titulo" class="bg-white p-4">
      <dt class="text-[11px] font-bold text-secundario">{{ dato.titulo }}</dt>
      <dd class="mt-1 text-[20px] font-extrabold tracking-[-0.02em]">{{ dato.valor }}</dd>
      <dd class="text-[11px] text-secundario">{{ dato.detalle }}</dd>
    </div>
  </dl>
</template>
