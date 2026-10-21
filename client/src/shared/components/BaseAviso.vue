<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ tono?: 'info' | 'error' | 'aviso' | 'exito'; titulo?: string }>(),
  { tono: 'info', titulo: undefined },
)

const estilos = {
  info: 'bg-rosa text-ciruela',
  error: 'bg-error-fondo text-error',
  aviso: 'bg-aviso-fondo text-aviso',
  exito: 'bg-exito-fondo text-exito',
}

// Los errores se anuncian de inmediato; el resto, sin interrumpir la lectura.
const rol = computed(() => (props.tono === 'error' ? 'alert' : 'status'))

const iconos = {
  info: 'M12 8h.01M11 12h1v4h1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z',
  error:
    'M12 8v5m0 3h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  aviso: 'M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z',
  exito: 'm5 12 4.5 4.5L19 7',
}
</script>

<template>
  <div
    :role="rol"
    class="flex animate-aparecer items-start gap-2.5 rounded-lg p-3.5 text-[13px]"
    :class="estilos[tono]"
  >
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      class="mt-0.5 size-[18px] shrink-0 fill-none stroke-current stroke-2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path :d="iconos[tono]" />
    </svg>
    <div>
      <strong v-if="titulo" class="block font-bold">{{ titulo }}</strong>
      <p class="leading-snug" :class="titulo ? 'mt-0.5 text-[12px]' : ''"><slot /></p>
    </div>
  </div>
</template>
