<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Asistente } from '../types'

/** Confirma bloquear o eliminar a una asistente, con un motivo opcional que queda en el historial. */
const props = defineProps<{
  accion: { tipo: 'bloquear' | 'eliminar'; asistente: Asistente } | null
  enviando: boolean
}>()
const emit = defineEmits<{ confirmar: [motivo: string | null]; cancelar: [] }>()

const motivo = ref('')
const idMotivo = useId()
watch(
  () => props.accion,
  () => (motivo.value = ''),
)

const nombre = computed(() =>
  props.accion ? `${props.accion.asistente.nombres} ${props.accion.asistente.apellidos}` : '',
)
const eliminar = computed(() => props.accion?.tipo === 'eliminar')

function confirmar() {
  emit('confirmar', motivo.value.trim() || null)
}
</script>

<template>
  <BaseDialogo
    :abierto="accion !== null"
    :titulo="eliminar ? `¿Eliminar a ${nombre}?` : `¿Bloquear a ${nombre}?`"
    @cerrar="emit('cancelar')"
  >
    <template #icono>
      <BaseIcono :nombre="eliminar ? 'alerta' : 'candado'" class="size-5" />
    </template>
    <ul class="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[13px] text-secundario">
      <template v-if="eliminar">
        <li>No podrá ingresar y sus sesiones abiertas se cerrarán.</li>
        <li>Su historial se conserva: si vuelve, podrás recuperar su cuenta.</li>
        <li>Lo que tenga pendiente seguirá disponible para las demás asistentes de tu equipo.</li>
      </template>
      <template v-else>
        <li>Se cerrarán sus sesiones abiertas.</li>
        <li>No podrá ingresar hasta que la desbloquees desde Mi equipo.</li>
      </template>
    </ul>
    <div class="mt-5 flex flex-col gap-1.5">
      <label :for="idMotivo" class="text-[12px] font-bold">Motivo (opcional)</label>
      <textarea
        :id="idMotivo"
        v-model="motivo"
        rows="2"
        maxlength="500"
        class="w-full resize-none rounded-[7px] border border-control px-3 py-2.5 text-[14px] transition-colors duration-200 hover:border-tinta"
      />
      <p class="text-[12px] text-secundario">Quedará en el historial de la cuenta.</p>
    </div>
    <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cancelar')">
        Cancelar
      </BaseBoton>
      <button
        v-if="eliminar"
        type="button"
        class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[9px] border border-error bg-error px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-[#8a2f34] disabled:opacity-70"
        :disabled="enviando"
        :aria-busy="enviando"
        @click="confirmar"
      >
        <span
          v-if="enviando"
          aria-hidden="true"
          class="size-4 animate-girar rounded-full border-2 border-current border-t-transparent"
        />
        Eliminar cuenta
      </button>
      <BaseBoton v-else :cargando="enviando" @click="confirmar">Bloquear cuenta</BaseBoton>
    </div>
  </BaseDialogo>
</template>
