<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { textoPorRol } from '../secciones'

// Lugar de cada sección mientras se construye: dice qué traerá para que el orden de trabajo sea
// visible. No simula datos ni acciones.
const route = useRoute()
const sesion = useSesionStore()

const contenido = computed(() => {
  const seccion = route.meta.seccion
  const rol = sesion.usuario?.rol
  if (!seccion || !rol) return null
  return {
    icono: seccion.icono,
    titulo: textoPorRol(seccion.etiqueta, rol),
    descripcion: textoPorRol(seccion.descripcion, rol),
  }
})
</script>

<template>
  <section v-if="contenido" aria-labelledby="titulo-seccion">
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      {{ contenido.titulo }}
    </h1>

    <div
      class="mt-6 flex flex-col items-center rounded-[14px] border border-dashed border-borde bg-white px-6 py-12 text-center sm:mt-8 sm:py-16 2xl:py-24"
    >
      <span
        aria-hidden="true"
        class="grid size-16 place-items-center rounded-[18px] bg-acento-suave text-acento motion-safe:animate-flotar"
      >
        <BaseIcono :nombre="contenido.icono" class="size-7" />
      </span>
      <span
        class="mt-6 inline-flex items-center gap-1.5 rounded-full bg-aviso-fondo px-3 py-1 text-[12px] font-bold text-aviso"
      >
        <BaseIcono nombre="destello" class="size-3.5" />
        Muy pronto
      </span>
      <p
        class="mt-4 max-w-[28ch] text-[20px] leading-snug font-extrabold tracking-[-0.02em] sm:text-[24px]"
      >
        Estaremos disponibles pronto, con todo y mejoras.
      </p>
      <p class="mt-3 max-w-[56ch] text-[14px] text-pretty text-secundario">
        {{ contenido.descripcion }}
      </p>
    </div>
  </section>
</template>
