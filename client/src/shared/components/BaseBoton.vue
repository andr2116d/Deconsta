<script setup lang="ts">
withDefaults(
  defineProps<{
    tipo?: 'button' | 'submit'
    variante?: 'principal' | 'secundario' | 'discreto'
    cargando?: boolean
    deshabilitado?: boolean
    ancho?: 'auto' | 'completo'
  }>(),
  { tipo: 'button', variante: 'principal', cargando: false, deshabilitado: false, ancho: 'auto' },
)

const estilos = {
  principal: 'border-ciruela bg-ciruela text-white enabled:hover:bg-ciruela-hover',
  secundario:
    'border-borde bg-white text-tinta enabled:hover:border-control enabled:hover:bg-fondo',
  discreto: 'border-transparent bg-transparent text-ciruela enabled:hover:bg-rosa',
}
</script>

<template>
  <button
    :type="tipo"
    :disabled="deshabilitado || cargando"
    :aria-busy="cargando"
    class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[9px] border px-4 text-[13px] font-bold transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-70"
    :class="[estilos[variante], ancho === 'completo' ? 'w-full' : '']"
  >
    <span
      v-if="cargando"
      aria-hidden="true"
      class="size-4 animate-girar rounded-full border-2 border-current border-t-transparent"
    />
    <slot />
  </button>
</template>
