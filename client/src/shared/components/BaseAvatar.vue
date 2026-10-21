<script setup lang="ts">
import { computed } from 'vue'

// Inicial de la cuenta sobre el acento de su rol. Es decorativo: el nombre se muestra o se anuncia
// junto a él.
const props = withDefaults(defineProps<{ nombre: string; tamano?: 'normal' | 'grande' }>(), {
  tamano: 'normal',
})

const inicial = computed(() => props.nombre.trim().slice(0, 1).toUpperCase())
</script>

<template>
  <span
    aria-hidden="true"
    class="grid shrink-0 place-items-center rounded-full bg-acento-suave font-extrabold text-acento"
    :class="tamano === 'grande' ? 'size-12 text-[17px]' : 'size-9 text-[13px]'"
  >
    {{ inicial }}
  </span>
</template>
