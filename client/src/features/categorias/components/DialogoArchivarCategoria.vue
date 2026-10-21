<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Categoria } from '../types'

/** Confirma el archivo de una categoría, con un motivo opcional que queda en el historial. */
const props = defineProps<{ categoria: Categoria | null; enviando: boolean }>()
const emit = defineEmits<{ confirmar: [motivo: string | null]; cancelar: [] }>()

const motivo = ref('')
const idMotivo = useId()
watch(
  () => props.categoria,
  () => (motivo.value = ''),
)

const titulo = computed(() => (props.categoria ? `¿Archivar «${props.categoria.nombre}»?` : ''))
</script>

<template>
  <BaseDialogo :abierto="categoria !== null" :titulo="titulo" @cerrar="emit('cancelar')">
    <template #icono>
      <BaseIcono nombre="archivo" class="size-5" />
    </template>
    <template v-if="categoria">
      <ul class="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[13px] text-secundario">
        <li>Ya no aparecerá al registrar deudas nuevas.</li>
        <li>Las deudas que ya la usan la conservan, también en el historial y al exportar.</li>
        <li>Puedes reactivarla cuando quieras desde «Archivadas».</li>
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
        <p class="text-[12px] text-secundario">Quedará en el historial.</p>
      </div>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cancelar')">
          Cancelar
        </BaseBoton>
        <BaseBoton :cargando="enviando" @click="emit('confirmar', motivo.trim() || null)">
          Archivar categoría
        </BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
