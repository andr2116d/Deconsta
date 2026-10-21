<script setup lang="ts">
import { ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

/** Confirma un cambio que relaja las reglas, con un motivo opcional que queda en el historial. */
const props = withDefaults(
  defineProps<{
    abierto: boolean
    titulo: string
    puntos: string[]
    confirmar: string
    enviando: boolean
    conMotivo?: boolean
  }>(),
  { conMotivo: false },
)
const emit = defineEmits<{ confirmar: [motivo: string | null]; cancelar: [] }>()

const motivo = ref('')
const idMotivo = useId()
watch(
  () => props.abierto,
  () => (motivo.value = ''),
)
</script>

<template>
  <BaseDialogo :abierto="abierto" :titulo="titulo" @cerrar="emit('cancelar')">
    <template #icono>
      <BaseIcono nombre="alerta" class="size-5" />
    </template>
    <ul class="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[13px] text-secundario">
      <li v-for="punto in puntos" :key="punto">{{ punto }}</li>
    </ul>
    <div v-if="conMotivo" class="mt-5 flex flex-col gap-1.5">
      <label :for="idMotivo" class="text-[12px] font-bold">Motivo (opcional)</label>
      <textarea
        :id="idMotivo"
        v-model="motivo"
        rows="2"
        maxlength="500"
        class="w-full resize-none rounded-[7px] border border-control px-3 py-2.5 text-[14px] transition-colors duration-200 hover:border-tinta"
      />
      <p class="text-[12px] text-secundario">Quedará en el historial.</p>
    </div>
    <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cancelar')">
        Cancelar
      </BaseBoton>
      <BaseBoton :cargando="enviando" @click="emit('confirmar', motivo.trim() || null)">
        {{ confirmar }}
      </BaseBoton>
    </div>
  </BaseDialogo>
</template>
