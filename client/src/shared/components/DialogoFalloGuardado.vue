<script setup lang="ts">
import { computed } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

/**
 * Explica, en orden, por qué no se guardó un cambio: qué pasó, qué campos revisar y qué hacer.
 * Solo ofrece reintentar cuando el fallo no depende de los datos (conexión o servicio).
 */
const props = defineProps<{
  error: ErrorApi | null
  titulo: string
  /** Nombre visible de cada campo, en el orden del formulario. */
  etiquetas: Record<string, string>
}>()
const emit = defineEmits<{ cerrar: []; reintentar: [] }>()

const campos = computed(() => {
  const error = props.error
  if (!error) return []
  return Object.entries(props.etiquetas)
    .filter(([campo]) => error.campos[campo])
    .map(([campo, etiqueta]) => ({ campo, etiqueta, mensaje: error.campos[campo] }))
})

const reintentable = computed(() => {
  const estado = props.error?.estado ?? 0
  return estado === 0 || estado >= 500
})
</script>

<template>
  <BaseDialogo :abierto="error !== null" :titulo="titulo" @cerrar="emit('cerrar')">
    <template #icono>
      <BaseIcono nombre="alerta" class="size-5" />
    </template>
    <template v-if="error">
      <p class="mt-2 text-[13px] text-secundario">{{ error.message }}</p>
      <ol v-if="campos.length" class="mt-4 flex flex-col gap-2">
        <li
          v-for="(item, indice) in campos"
          :key="item.campo"
          class="flex gap-3 rounded-lg bg-error-fondo p-3 text-[13px] text-error"
        >
          <span
            aria-hidden="true"
            class="grid size-5 shrink-0 place-items-center rounded-full bg-error text-[11px] font-bold text-white"
          >
            {{ indice + 1 }}
          </span>
          <span>
            <strong class="block font-bold">{{ item.etiqueta }}</strong>
            {{ item.mensaje }}
          </span>
        </li>
      </ol>
      <p v-if="error.referencia" class="mt-3 text-[12px] text-secundario">
        Referencia para soporte: <span class="font-bold">{{ error.referencia }}</span>
      </p>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton :variante="reintentable ? 'secundario' : 'principal'" @click="emit('cerrar')">
          {{ campos.length ? 'Revisar mis datos' : 'Entendido' }}
        </BaseBoton>
        <BaseBoton v-if="reintentable" @click="emit('reintentar')">Reintentar</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
