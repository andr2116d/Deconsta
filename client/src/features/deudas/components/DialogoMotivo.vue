<script setup lang="ts">
import { ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

/** Rechazar o anular siempre deja un motivo: la asistente lo ve en su aviso. */
const props = defineProps<{
  abierto: boolean
  accion: 'rechazar' | 'anular'
  concepto: string
  enviando: boolean
  error?: string
}>()
const emit = defineEmits<{ confirmar: [motivo: string]; cerrar: [] }>()

const motivo = ref('')
const id = useId()
watch(
  () => props.abierto,
  (abierto) => abierto && (motivo.value = ''),
)
</script>

<template>
  <BaseDialogo
    :abierto="abierto"
    :titulo="
      accion === 'rechazar' ? 'Rechaza la deuda con contexto.' : 'Anula la deuda con contexto.'
    "
    @cerrar="emit('cerrar')"
  >
    <template #icono>
      <BaseIcono nombre="alerta" class="size-5" />
    </template>
    <p class="mt-3 text-[13px] text-secundario">
      «{{ concepto }}»
      {{
        accion === 'rechazar'
          ? 'no se pagará. Tu asistente verá el motivo.'
          : 'dejará de estar en la agenda y no se pagará. Tu asistente verá el motivo.'
      }}
    </p>
    <form class="mt-4" novalidate @submit.prevent="emit('confirmar', motivo)">
      <label :for="id" class="text-[12px] font-bold">Motivo</label>
      <textarea
        :id="id"
        v-model="motivo"
        rows="3"
        maxlength="500"
        :aria-invalid="error ? 'true' : undefined"
        placeholder="Por ejemplo: el recibo es de la casa de mi hermano, no corresponde."
        class="mt-1.5 w-full rounded-[7px] border bg-white px-3 py-2.5 text-[14px]"
        :class="error ? 'border-error' : 'border-control hover:border-tinta'"
      />
      <p v-if="error" class="mt-1 text-[12px] text-error">{{ error }}</p>
      <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="discreto" @click="emit('cerrar')">Volver</BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando">
          {{ accion === 'rechazar' ? 'Rechazar deuda' : 'Anular deuda' }}
        </BaseBoton>
      </div>
    </form>
  </BaseDialogo>
</template>
