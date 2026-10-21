<script setup lang="ts">
// Dos trazos de distinto largo e inclinados: una obligación y su comprobación.
withDefaults(defineProps<{ tamano?: 'normal' | 'gigante' }>(), { tamano: 'normal' })
</script>

<template>
  <span
    class="inline-flex items-center font-extrabold tracking-[-0.04em] text-ciruela"
    :class="tamano === 'gigante' ? 'text-[clamp(64px,15vw,190px)] leading-none' : 'text-[26px]'"
  >
    <span
      aria-hidden="true"
      class="inline-flex -rotate-[25deg]"
      :class="tamano === 'gigante' ? 'mr-[0.08em] gap-[0.05em]' : 'mr-1.5 gap-[3px]'"
    >
      <i
        class="block rounded-full bg-current"
        :class="tamano === 'gigante' ? 'h-[0.52em] w-[0.075em]' : 'h-[21px] w-[5px]'"
      />
      <i
        class="block rounded-full bg-current opacity-60"
        :class="
          tamano === 'gigante' ? 'mt-[0.18em] h-[0.34em] w-[0.075em]' : 'mt-2 h-[13px] w-[5px]'
        "
      />
    </span>
    Deconsta
  </span>
</template>
