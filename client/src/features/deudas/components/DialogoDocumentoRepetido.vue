<script setup lang="ts">
import { computed } from 'vue'

import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { DeudaExistente } from '../types'

/** El documento ya respalda otra deuda: dónde se usó y qué hacer. */
const props = defineProps<{
  deuda: DeudaExistente | null
  /** Con este intento se bloqueó el registro de deudas de la asistente. */
  bloqueado: boolean
}>()
const emit = defineEmits<{ cerrar: []; otro: [] }>()

const fecha = new Intl.DateTimeFormat('es-PE', { dateStyle: 'long', timeZone: 'America/Lima' })
const registrada = computed(() =>
  props.deuda ? fecha.format(new Date(props.deuda.registrada_en)) : '',
)
</script>

<template>
  <BaseDialogo
    :abierto="deuda !== null"
    titulo="Este documento ya lo usaste."
    @cerrar="emit('cerrar')"
  >
    <template #icono>
      <BaseIcono nombre="documento" class="size-5" />
    </template>
    <template v-if="deuda">
      <p class="mt-3 text-[13px] text-secundario">
        Cada recibo, boleta o cronograma respalda una sola deuda. Este ya está en:
      </p>
      <div class="mt-3 rounded-[10px] border border-dashed border-borde px-4 py-3">
        <strong class="block text-[14px]">{{ deuda.concepto }}</strong>
        <small class="text-[12px] text-secundario">Registrada el {{ registrada }}</small>
      </div>
      <BaseAviso v-if="bloqueado" tono="error" class="mt-4" titulo="Registro de deudas en pausa">
        Lo intentaste varias veces con documentos ya usados. Tu gerente ya lo sabe y puede
        permitirte registrar otra vez. Mientras tanto, puedes seguir con tus demás tareas.
      </BaseAviso>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="discreto" @click="emit('cerrar')">Entendido</BaseBoton>
        <BaseBoton v-if="!bloqueado" @click="emit('otro')">Elegir otro documento</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
