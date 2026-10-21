<script setup lang="ts">
import FormularioCambioContrasena from '@/features/acceso/components/FormularioCambioContrasena.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

// Recomendado, no obligatorio: «Ahora no» lo pospone hasta el siguiente ingreso y se recordará en
// cada uno mientras siga siendo temporal.
const emit = defineEmits<{ posponer: []; 'sesion-terminada': [] }>()
</script>

<template>
  <section
    class="animate-aparecer rounded-[14px] border border-borde bg-white p-6 sm:p-9"
    aria-labelledby="titulo-contrasena"
  >
    <span
      aria-hidden="true"
      class="mb-5 grid size-12 place-items-center rounded-[13px] bg-acento-suave text-acento"
    >
      <BaseIcono nombre="candado" class="size-[22px]" />
    </span>
    <h1
      id="titulo-contrasena"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[30px]"
    >
      Crea tu contraseña personal.
    </h1>
    <p class="mt-2 mb-6 max-w-[56ch] text-[13px] text-secundario">
      Tu gerente conoce la contraseña temporal con la que entraste. Reemplázala por una que solo tú
      conozcas.
    </p>
    <div class="max-w-[440px]">
      <FormularioCambioContrasena inicial @sesion-terminada="emit('sesion-terminada')" />
      <BaseBoton variante="discreto" ancho="completo" class="mt-2" @click="emit('posponer')">
        Ahora no, lo haré después
      </BaseBoton>
    </div>
  </section>
</template>
