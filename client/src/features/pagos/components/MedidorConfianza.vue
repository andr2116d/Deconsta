<script setup lang="ts">
import { computed } from 'vue'

/**
 * Cuánto respaldan los comprobantes el pago. Nunca llega a 100: una captura no se confirma del todo
 * sin mirar la cuenta que recibió el dinero.
 */
const props = defineProps<{ confianza: number }>()

const nivel = computed(() => {
  if (props.confianza >= 80)
    return { texto: 'Confianza alta', clase: 'text-exito', trazo: 'stroke-exito' }
  if (props.confianza >= 60)
    return { texto: 'Confianza media', clase: 'text-aviso', trazo: 'stroke-aviso' }
  return { texto: 'Confianza baja', clase: 'text-error', trazo: 'stroke-error' }
})
const RADIO = 34
const CIRCUNFERENCIA = 2 * Math.PI * RADIO
const avance = computed(() => CIRCUNFERENCIA * (1 - props.confianza / 100))
</script>

<template>
  <div class="flex items-center gap-4">
    <svg
      viewBox="0 0 80 80"
      class="size-20 shrink-0 -rotate-90"
      role="img"
      :aria-label="`${nivel.texto}: ${confianza} de 100`"
    >
      <circle cx="40" cy="40" :r="RADIO" fill="none" stroke-width="8" class="stroke-fondo" />
      <circle
        cx="40"
        cy="40"
        :r="RADIO"
        fill="none"
        stroke-width="8"
        stroke-linecap="round"
        :class="nivel.trazo"
        :stroke-dasharray="CIRCUNFERENCIA"
        :stroke-dashoffset="avance"
        class="transition-[stroke-dashoffset] duration-700 motion-reduce:transition-none"
      />
    </svg>
    <div>
      <p class="text-[28px] leading-none font-extrabold tracking-[-0.03em]" :class="nivel.clase">
        {{ confianza }} %
      </p>
      <p class="mt-1 text-[13px] font-bold" :class="nivel.clase">{{ nivel.texto }}</p>
      <p class="mt-1 max-w-[30ch] text-[11px] text-secundario">
        Nunca llega a 100: si puedes, mira que el dinero haya llegado a la cuenta del servicio.
      </p>
    </div>
  </div>
</template>
