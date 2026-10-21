<script setup lang="ts">
import { trazos, type NombreIcono } from './iconos'

// Decorativo: el texto que lo acompaña, o un aria-label en el control, es lo que se anuncia.
defineProps<{ nombre: NombreIcono }>()
</script>

<template>
  <svg
    aria-hidden="true"
    focusable="false"
    viewBox="0 0 24 24"
    class="shrink-0 fill-none stroke-current stroke-2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path :d="trazos[nombre]" />
  </svg>
</template>
