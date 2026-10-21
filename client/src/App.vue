<script setup lang="ts">
import { watchEffect } from 'vue'
import { RouterView } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'

const sesion = useSesionStore()

// El acento de color sigue al rol de la cuenta (main.css); sin sesión, el de la marca.
watchEffect(() => {
  const rol = sesion.usuario?.rol
  if (rol) document.documentElement.dataset.rol = rol
  else delete document.documentElement.dataset.rol
})
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition name="vista" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
</template>
