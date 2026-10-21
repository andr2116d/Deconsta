<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import { formatearSoles } from '@/features/reglas/importes'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { ESTADOS, formatearFecha, MOTIVOS } from '../catalogo'
import type { RegistroDeuda } from '../types'

/** Cierre del registro: qué quedó, en qué estado y qué sigue. */
const props = defineProps<{ registro: RegistroDeuda; rol: Rol }>()
const emit = defineEmits<{ otra: [] }>()

const deuda = computed(() => props.registro.deuda)
const espera = computed(() => deuda.value.estado === 'por_autorizar')
const titulo = computed(() =>
  espera.value ? 'Se envió a tu gerente.' : 'Ya tiene lugar en tu agenda.',
)
const texto = computed(() => {
  if (espera.value)
    return 'La deuda quedó registrada, pero no se pagará hasta que tu gerente la autorice. Le llegó un aviso con el motivo.'
  if (props.rol === 'asistente')
    return 'Ya se puede pagar. Tu gerente recibió un aviso y puede revisarla cuando tenga tiempo.'
  return 'Ya se puede pagar. Podrás asignar su pago desde su detalle.'
})
</script>

<template>
  <section
    class="mx-auto max-w-[650px] animate-aparecer rounded-2xl border border-borde bg-white px-5 py-8 text-center sm:px-11 sm:py-11"
    aria-labelledby="titulo-seccion"
  >
    <span
      aria-hidden="true"
      class="mx-auto mb-5 grid size-16 place-items-center rounded-full"
      :class="espera ? 'bg-aviso-fondo text-aviso' : 'bg-exito-fondo text-exito'"
    >
      <BaseIcono :nombre="espera ? 'reloj' : 'check'" class="size-[30px]" />
    </span>
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[25px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[29px]"
    >
      {{ titulo }}
    </h1>
    <p class="mx-auto mt-3 max-w-[440px] text-[13px] text-secundario">{{ texto }}</p>

    <dl
      class="my-6 grid grid-cols-1 gap-4 border-y border-dashed border-borde py-5 text-left sm:grid-cols-3"
    >
      <div>
        <dt class="text-[11px] text-secundario">Deuda</dt>
        <dd class="text-[14px] font-bold">{{ deuda.concepto }}</dd>
      </div>
      <div>
        <dt class="text-[11px] text-secundario">
          {{ deuda.cuotas.length > 1 ? `${deuda.cuotas.length} cuotas` : 'Importe' }}
        </dt>
        <dd class="text-[14px] font-bold">{{ formatearSoles(deuda.importe) }}</dd>
        <dd class="text-[11px] text-secundario">Vence el {{ formatearFecha(deuda.vence_el) }}</dd>
      </div>
      <div>
        <dt class="text-[11px] text-secundario">Estado</dt>
        <dd>
          <span
            class="inline-flex rounded-md px-2 py-0.5 text-[11px] font-bold"
            :class="ESTADOS[deuda.estado].clase"
          >
            {{ ESTADOS[deuda.estado].texto }}
          </span>
        </dd>
      </div>
    </dl>

    <ul v-if="deuda.motivos.length" class="mb-6 flex flex-wrap justify-center gap-2">
      <li
        v-for="motivo in deuda.motivos"
        :key="motivo"
        class="rounded-full bg-aviso-fondo px-3 py-1 text-[12px] font-bold text-aviso"
      >
        {{ MOTIVOS[motivo] }}
      </li>
    </ul>
    <BaseAviso
      v-if="registro.avisos.length"
      tono="aviso"
      class="mb-6 text-left"
      titulo="Ten en cuenta"
    >
      {{ registro.avisos.join(' ') }}
    </BaseAviso>

    <div class="flex flex-col justify-center gap-2 sm:flex-row">
      <BaseBoton @click="emit('otra')">
        <BaseIcono nombre="mas" class="size-4" />
        Registrar otra deuda
      </BaseBoton>
      <RouterLink
        :to="{ name: 'inicio' }"
        class="inline-flex min-h-11 items-center justify-center rounded-[9px] px-4 text-[13px] font-bold text-acento transition-colors duration-200 hover:bg-acento-suave"
      >
        Volver a mi trabajo
      </RouterLink>
    </div>
  </section>
</template>
