<script setup lang="ts">
import { computed } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { formatearCelular } from '../credenciales'
import type { Asistente } from '../types'

const props = defineProps<{ asistente: Asistente; ocupada: boolean }>()
const emit = defineEmits<{ bloquear: []; desbloquear: []; eliminar: [] }>()

const nombre = computed(() => `${props.asistente.nombres} ${props.asistente.apellidos}`)
const inicial = computed(() => props.asistente.nombres.trim().slice(0, 1).toUpperCase())

const ESTADOS = {
  activa: { texto: 'Acceso activo', clase: 'bg-exito-fondo text-exito' },
  pendiente: { texto: 'Primer ingreso pendiente', clase: 'bg-aviso-fondo text-aviso' },
  bloqueada: { texto: 'Bloqueada', clase: 'bg-error-fondo text-error' },
} as const

const estado = computed(() => ESTADOS[props.asistente.estado])
const detalleBloqueo = computed(() => {
  if (!props.asistente.bloqueada) return null
  return props.asistente.causa_bloqueo === 'gerente'
    ? 'La bloqueaste tú. No puede ingresar hasta que la desbloquees.'
    : 'Se bloqueó tras 5 intentos fallidos. Desbloquéala si reconoces los intentos.'
})

const fecha = new Intl.DateTimeFormat('es-PE', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Lima',
})
const ultimoIngreso = computed(() =>
  props.asistente.ultimo_ingreso_en
    ? fecha.format(new Date(props.asistente.ultimo_ingreso_en))
    : 'Todavía no ingresa',
)
</script>

<template>
  <article
    class="animate-aparecer rounded-[14px] border border-borde bg-white p-5 transition-shadow duration-200 hover:shadow-[0_12px_40px_#30233014] sm:p-6"
    :aria-labelledby="`asistente-${asistente.id}`"
  >
    <div class="flex flex-wrap items-center gap-3">
      <span
        aria-hidden="true"
        class="grid size-11 shrink-0 place-items-center rounded-full bg-[#e0eae3] text-[15px] font-extrabold text-[#365c4b]"
      >
        {{ inicial }}
      </span>
      <div class="min-w-0 flex-1">
        <h2 :id="`asistente-${asistente.id}`" class="truncate text-[16px] font-extrabold">
          {{ nombre }}
        </h2>
        <p class="text-[12px] text-secundario">{{ asistente.cargo ?? 'Asistente' }}</p>
      </div>
      <span
        class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-bold"
        :class="estado.clase"
      >
        <span aria-hidden="true" class="size-1.5 rounded-full bg-current" />
        {{ estado.texto }}
      </span>
    </div>

    <dl class="mt-4 grid gap-x-6 gap-y-3 border-y border-borde py-4 text-[12px] sm:grid-cols-2">
      <div>
        <dt class="text-secundario">Usuario</dt>
        <dd class="font-bold break-all">@{{ asistente.nombre_usuario }}</dd>
      </div>
      <div>
        <dt class="text-secundario">Celular</dt>
        <dd class="font-bold">{{ formatearCelular(asistente.telefono) ?? 'Sin registrar' }}</dd>
      </div>
      <div>
        <dt class="text-secundario">
          {{ asistente.tipo_documento === 'dni' ? 'DNI' : 'Carné de extranjería' }}
        </dt>
        <dd class="font-bold">
          <span class="sr-only">terminado en</span>
          {{ asistente.documento }}
        </dd>
      </div>
      <div>
        <dt class="text-secundario">Correo</dt>
        <dd
          class="font-bold break-all"
          :class="asistente.correo ? '' : 'font-normal text-secundario'"
        >
          {{ asistente.correo ?? 'Lo completará en su primer ingreso' }}
        </dd>
      </div>
      <div>
        <dt class="text-secundario">Último ingreso</dt>
        <dd class="font-bold">{{ ultimoIngreso }}</dd>
      </div>
    </dl>

    <p v-if="detalleBloqueo" class="mt-3 text-[12px] text-error">{{ detalleBloqueo }}</p>

    <div class="mt-4 flex flex-wrap items-center justify-end gap-2">
      <BaseBoton
        v-if="asistente.bloqueada"
        variante="secundario"
        :cargando="ocupada"
        @click="emit('desbloquear')"
      >
        <BaseIcono nombre="candado" class="size-4" />
        Desbloquear
      </BaseBoton>
      <BaseBoton v-else variante="secundario" :deshabilitado="ocupada" @click="emit('bloquear')">
        <BaseIcono nombre="candado" class="size-4" />
        Bloquear
      </BaseBoton>
      <button
        type="button"
        class="inline-flex min-h-11 items-center gap-2 rounded-[9px] px-4 text-[13px] font-bold text-error transition-colors duration-200 hover:bg-error-fondo disabled:opacity-70"
        :disabled="ocupada"
        @click="emit('eliminar')"
      >
        <BaseIcono nombre="cerrar" class="size-4" />
        Eliminar
      </button>
    </div>
  </article>
</template>
