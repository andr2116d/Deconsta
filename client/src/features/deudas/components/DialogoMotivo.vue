<script setup lang="ts">
import { ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

/** Rechazar o anular una deuda, o devolver un pago, siempre deja un motivo: la asistente lo ve. */
const props = defineProps<{
  abierto: boolean
  accion: 'rechazar' | 'anular' | 'devolver'
  concepto: string
  enviando: boolean
  error?: string
}>()
const emit = defineEmits<{ confirmar: [motivo: string]; cerrar: [] }>()

const TEXTOS = {
  rechazar: {
    titulo: 'Rechaza la deuda con contexto.',
    detalle: 'no se pagará. Tu asistente verá el motivo.',
    ejemplo: 'Por ejemplo: el recibo es de la casa de mi hermano, no corresponde.',
    boton: 'Rechazar deuda',
  },
  anular: {
    titulo: 'Anula la deuda con contexto.',
    detalle: 'dejará de estar en la agenda y no se pagará. Tu asistente verá el motivo.',
    ejemplo: 'Por ejemplo: el recibo es de la casa de mi hermano, no corresponde.',
    boton: 'Anular deuda',
  },
  devolver: {
    titulo: 'Devuelve el pago con contexto.',
    detalle: 'volverá a estar por pagar. Tu asistente verá el motivo y subirá otro comprobante.',
    ejemplo: 'Por ejemplo: el voucher es de otro mes, el importe no llegó a la cuenta.',
    boton: 'Devolver pago',
  },
}

const motivo = ref('')
const id = useId()
watch(
  () => props.abierto,
  (abierto) => abierto && (motivo.value = ''),
)
</script>

<template>
  <BaseDialogo :abierto="abierto" :titulo="TEXTOS[accion].titulo" @cerrar="emit('cerrar')">
    <template #icono>
      <BaseIcono nombre="alerta" class="size-5" />
    </template>
    <p class="mt-3 text-[13px] text-secundario">
      «{{ concepto }}»
      {{ TEXTOS[accion].detalle }}
    </p>
    <form class="mt-4" novalidate @submit.prevent="emit('confirmar', motivo)">
      <label :for="id" class="text-[12px] font-bold">Motivo</label>
      <textarea
        :id="id"
        v-model="motivo"
        rows="3"
        maxlength="500"
        :aria-invalid="error ? 'true' : undefined"
        :placeholder="TEXTOS[accion].ejemplo"
        class="mt-1.5 w-full rounded-[7px] border bg-white px-3 py-2.5 text-[14px]"
        :class="error ? 'border-error' : 'border-control hover:border-tinta'"
      />
      <p v-if="error" class="mt-1 text-[12px] text-error">{{ error }}</p>
      <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="discreto" @click="emit('cerrar')">Volver</BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando">
          {{ TEXTOS[accion].boton }}
        </BaseBoton>
      </div>
    </form>
  </BaseDialogo>
</template>
