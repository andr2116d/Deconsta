<script setup lang="ts">
import { computed } from 'vue'

import BaseAvatar from '@/shared/components/BaseAvatar.vue'

import { formatearDiaYMes } from '../datos'
import type { Cuenta } from '../types'

// Tarjeta lateral de «Mi cuenta»: quién es la cuenta de un vistazo. Se actualiza al guardar.
const props = defineProps<{ cuenta: Cuenta | null }>()

const esGerente = computed(() => props.cuenta?.rol === 'gerente')
const cupo = computed(() => props.cuenta?.cambios_nombre_usuario)
</script>

<template>
  <aside
    aria-label="Resumen de tu cuenta"
    class="self-start rounded-[14px] bg-acento-suave p-5 lg:sticky lg:top-[156px] lg:p-6"
  >
    <template v-if="cuenta">
      <!-- En pantallas angostas, una franja compacta: el formulario queda a la vista. -->
      <div class="flex items-center gap-4 lg:block">
        <BaseAvatar :nombre="cuenta.nombres" tamano="grande" class="!bg-white" />
        <div class="min-w-0">
          <h2
            class="text-[18px] leading-tight font-extrabold tracking-[-0.03em] break-words lg:mt-5 lg:text-[22px]"
          >
            {{ cuenta.nombres }} {{ cuenta.apellidos }}
          </h2>
          <p class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 lg:mt-3 lg:block">
            <span
              class="inline-flex rounded-md bg-acento px-2.5 py-1 text-[11px] font-bold text-white"
            >
              {{ esGerente ? 'Gerente' : 'Asistente' }}
            </span>
            <span
              class="text-[13px] lg:mt-3 lg:block"
              :class="cuenta.cargo ? 'text-acento' : 'text-secundario'"
            >
              {{ cuenta.cargo ?? 'Sin cargo asignado' }}
            </span>
          </p>
        </div>
      </div>

      <dl class="mt-5 hidden text-[12px] lg:block">
        <div class="border-t border-acento/15 py-3">
          <dt class="text-secundario">Usuario de acceso</dt>
          <dd class="mt-0.5 font-bold break-all">@{{ cuenta.nombre_usuario }}</dd>
        </div>
        <div v-if="cupo" class="border-t border-acento/15 py-3">
          <dt class="text-secundario">Cambios de usuario este mes</dt>
          <dd class="mt-0.5 font-bold">
            {{ cupo.restantes }} de {{ cupo.maximo }} disponibles
            <span class="block font-normal text-secundario">
              Se renuevan el {{ formatearDiaYMes(cupo.renueva_en) }}
            </span>
          </dd>
        </div>
      </dl>
      <p class="mt-3 hidden text-[12px] text-secundario lg:block">
        {{
          esGerente
            ? 'Tienes la decisión final sobre cada pago.'
            : 'Tus acciones quedan asociadas a esta cuenta.'
        }}
      </p>
    </template>

    <div v-else aria-hidden="true" class="motion-safe:animate-pulse">
      <div class="size-12 rounded-full bg-white" />
      <div class="mt-5 h-6 w-3/4 rounded bg-white/80" />
      <div class="mt-3 h-5 w-20 rounded bg-white/80" />
      <div class="mt-6 h-10 rounded bg-white/60" />
      <div class="mt-3 h-10 rounded bg-white/60" />
    </div>
  </aside>
</template>
