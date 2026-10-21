<script setup lang="ts">
// Contenedor de cada bloque de «Mi cuenta». Mientras llegan los datos muestra un esqueleto con la
// forma del formulario, sin anunciarlo como contenido.
withDefaults(defineProps<{ titulo: string; descripcion?: string; cargando?: boolean }>(), {
  descripcion: undefined,
  cargando: false,
})
</script>

<template>
  <section
    class="rounded-[14px] border border-borde bg-white p-5 sm:p-7"
    :aria-busy="cargando"
    :aria-label="titulo"
  >
    <h2 class="text-[19px] leading-tight font-extrabold tracking-[-0.02em]">{{ titulo }}</h2>
    <p v-if="descripcion" class="mt-1.5 mb-6 text-[13px] text-secundario">{{ descripcion }}</p>
    <div
      v-if="cargando"
      aria-hidden="true"
      class="grid gap-4 motion-safe:animate-pulse sm:grid-cols-2"
    >
      <div v-for="n in 4" :key="n">
        <div class="mb-2 h-3 w-24 rounded bg-fondo" />
        <div class="h-[46px] rounded-[7px] bg-fondo" />
      </div>
    </div>
    <slot v-else />
  </section>
</template>
