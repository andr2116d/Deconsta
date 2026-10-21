<script setup lang="ts">
import FormularioCambioContrasena from '@/features/acceso/components/FormularioCambioContrasena.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'

// Obligatoria: no se cierra con Escape ni con un botón. La única salida es cerrar la sesión.
// Al guardar, la sesión pasa al paso siguiente y la vista que la contiene la retira.
const emit = defineEmits<{ salir: []; 'sesion-terminada': [] }>()
defineProps<{ saliendo: boolean }>()
</script>

<template>
  <BaseDialogo abierto obligatorio titulo="Crea tu contraseña personal.">
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
      Ingresaste con una contraseña temporal. Para entrar a tu espacio, reemplázala por una que solo
      tú conozcas.
    </p>
    <FormularioCambioContrasena inicial @sesion-terminada="emit('sesion-terminada')" />
    <BaseBoton
      variante="discreto"
      ancho="completo"
      class="mt-2"
      :cargando="saliendo"
      @click="emit('salir')"
    >
      Salir de la sesión
    </BaseBoton>
  </BaseDialogo>
</template>
