<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import BaseAvatar from '@/shared/components/BaseAvatar.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Titular } from '../types'

/**
 * Quiénes pueden figurar como titulares sin pedir tu autorización: tú (con tus datos de Mi cuenta)
 * y las personas o empresas que agregues.
 */
const props = defineProps<{
  titulares: Titular[]
  maximo: number
  nombreGerente: string
  ocupado: string | null
}>()
const emit = defineEmits<{ agregar: []; editar: [titular: Titular]; quitar: [titular: Titular] }>()

const ETIQUETAS_TIPO = { dni: 'DNI', ce: 'Carné', ruc: 'RUC' }
const lleno = computed(() => props.titulares.length >= props.maximo)
</script>

<template>
  <section
    aria-labelledby="titulo-titulares"
    class="rounded-[14px] border border-borde bg-white p-5 sm:p-6"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 id="titulo-titulares" class="text-[17px] font-extrabold">Titulares autorizados</h2>
        <p class="mt-1 max-w-[52ch] text-[13px] text-secundario">
          Si un recibo está a nombre de otra persona, esperará tu autorización. Agrega aquí a
          quienes pagas a menudo, como tu esposa o tu empresa, para que no la pidan.
        </p>
      </div>
      <BaseBoton variante="secundario" :deshabilitado="lleno" @click="emit('agregar')">
        <BaseIcono nombre="mas" class="size-4" />
        Agregar titular
      </BaseBoton>
    </div>

    <ul class="mt-4" aria-label="Titulares reconocidos">
      <li class="flex items-center gap-3 border-b border-borde py-3.5">
        <BaseAvatar :nombre="nombreGerente" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-[14px] font-extrabold">
            {{ nombreGerente }} <span class="font-semibold text-secundario">· Tú</span>
          </p>
          <p class="text-[12px] text-secundario">
            Con tu nombre, tu documento y tu nombre en recibos.
            <RouterLink :to="{ name: 'mis-datos' }" class="font-bold text-acento hover:underline">
              Revisarlos en Mi cuenta
            </RouterLink>
          </p>
        </div>
        <span class="rounded-md bg-exito-fondo px-2 py-1 text-[11px] font-bold text-exito">
          Siempre
        </span>
      </li>
      <TransitionGroup
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        leave-active-class="transition duration-200 ease-in"
        leave-to-class="opacity-0 -translate-x-2"
      >
        <li
          v-for="titular in titulares"
          :key="titular.id"
          class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-borde py-3.5 last:border-b-0"
        >
          <BaseAvatar :nombre="titular.nombre" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-[14px] font-extrabold">{{ titular.nombre }}</p>
            <p class="text-[12px] text-secundario">
              <template v-if="titular.relacion">{{ titular.relacion }} · </template>
              <template v-if="titular.tipo_documento">
                {{ ETIQUETAS_TIPO[titular.tipo_documento] }}
                <span class="sr-only">terminado en</span>
                {{ titular.documento }}
              </template>
              <template v-else>Sin documento</template>
            </p>
          </div>
          <div class="flex w-full justify-end gap-1 pl-12 sm:w-auto sm:pl-0">
            <BaseBoton
              variante="discreto"
              :deshabilitado="ocupado === titular.id"
              @click="emit('editar', titular)"
            >
              <BaseIcono nombre="lapiz" class="size-4" />
              Editar
              <span class="sr-only">{{ titular.nombre }}</span>
            </BaseBoton>
            <BaseBoton
              variante="discreto"
              :cargando="ocupado === titular.id"
              @click="emit('quitar', titular)"
            >
              <BaseIcono v-if="ocupado !== titular.id" nombre="cerrar" class="size-4" />
              Quitar
              <span class="sr-only">{{ titular.nombre }}</span>
            </BaseBoton>
          </div>
        </li>
      </TransitionGroup>
    </ul>

    <p class="mt-3 text-[12px] text-secundario" aria-live="polite">
      <template v-if="lleno">
        Llegaste al máximo de {{ maximo }} titulares. Quita alguno para agregar otro.
      </template>
      <template v-else>{{ titulares.length }} de {{ maximo }} titulares agregados.</template>
    </p>
  </section>
</template>
