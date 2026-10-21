<script setup lang="ts">
import { RouterView } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'

import PestanasSeccion from '../components/PestanasSeccion.vue'

// Marco de «Límites y categorías»: el encabezado y las pestañas se quedan; solo cambia el
// contenido de la pestaña (reglas de autorización o categorías).
const sesion = useSesionStore()
</script>

<template>
  <section v-if="sesion.usuario" aria-labelledby="titulo-seccion">
    <header class="mb-5 sm:mb-6">
      <h1
        id="titulo-seccion"
        tabindex="-1"
        class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
      >
        Las reglas de tu espacio.
      </h1>
      <p class="mt-2 max-w-[62ch] text-[13px] text-secundario">
        Decide qué necesita tu autorización y cómo se ordenan tus deudas. Solo tú puedes cambiarlo.
      </p>
    </header>

    <PestanasSeccion
      grupo="configuracion"
      :rol="sesion.usuario.rol"
      etiqueta="Secciones de Límites y categorías"
    />

    <RouterView v-slot="{ Component, route: actual }">
      <Transition name="vista" mode="out-in">
        <component :is="Component" :key="actual.name" />
      </Transition>
    </RouterView>
  </section>
</template>
