<script setup lang="ts">
import FormularioCambioContrasena from '@/features/acceso/components/FormularioCambioContrasena.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'

// Recordatorio de la contraseña temporal: se puede cerrar (Escape, la X o «Ahora no») y vuelve en
// el siguiente ingreso mientras el backend la siga marcando como temporal.
const emit = defineEmits<{ cerrar: []; cambiada: []; 'sesion-terminada': [] }>()
</script>

<template>
  <BaseDialogo abierto titulo="Crea tu contraseña personal." @cerrar="emit('cerrar')">
    <template #icono>
      <svg
        viewBox="0 0 24 24"
        class="size-5 fill-none stroke-current stroke-2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z" />
      </svg>
    </template>
    <p class="mt-2 mb-5 text-[13px] text-secundario">
      Sigues usando la contraseña temporal que te entregaron. Reemplázala por una que solo tú
      conozcas; te lo recordaremos en cada ingreso hasta que lo hagas.
    </p>
    <FormularioCambioContrasena
      inicial
      @cambiada="emit('cambiada')"
      @sesion-terminada="emit('sesion-terminada')"
    />
    <BaseBoton variante="discreto" ancho="completo" class="mt-2" @click="emit('cerrar')">
      Ahora no
    </BaseBoton>
  </BaseDialogo>
</template>
