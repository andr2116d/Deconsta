<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'

import { descargarDocumento } from '../api/deudas'

/**
 * Muestra el archivo de una deuda. Llega por la API, con la sesión, como un blob local: no hay
 * enlaces públicos ni el archivo queda en la caché del navegador.
 */
const props = defineProps<{ documentoId: string; tipo: string; titulo: string }>()

const url = ref<string | null>(null)
const fallo = ref<string | null>(null)
let turno = 0

function liberar() {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = null
}

async function cargar(id: string) {
  const propio = ++turno
  liberar()
  fallo.value = null
  try {
    const archivo = await descargarDocumento(id)
    if (propio === turno) url.value = URL.createObjectURL(archivo)
  } catch (error) {
    if (propio === turno)
      fallo.value = error instanceof ErrorApi ? error.message : 'No pudimos mostrar el documento.'
  }
}

watch(() => props.documentoId, cargar, { immediate: true })
onBeforeUnmount(() => {
  turno += 1
  liberar()
})
</script>

<template>
  <div class="flex min-h-[280px] items-center justify-center rounded-xl bg-[#ede8ed] p-4">
    <p v-if="fallo" role="alert" class="text-center text-[12px] text-error">{{ fallo }}</p>
    <span
      v-else-if="!url"
      aria-label="Cargando el documento"
      class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
    />
    <img
      v-else-if="tipo !== 'application/pdf'"
      :src="url"
      :alt="titulo"
      class="max-h-[460px] max-w-full rounded-[4px] object-contain shadow-[0_9px_30px_#30233024]"
    />
    <object
      v-else
      :data="url"
      type="application/pdf"
      :aria-label="titulo"
      class="h-[460px] w-full rounded-[4px] bg-white"
    >
      <a :href="url" target="_blank" rel="noopener" class="font-bold text-acento underline">
        Abrir el PDF
      </a>
    </object>
  </div>
</template>
