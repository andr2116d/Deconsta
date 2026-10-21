<script setup lang="ts">
import { useRouter } from 'vue-router'

import FormularioCambioContrasena from '../components/FormularioCambioContrasena.vue'
import MarcoAcceso from '../components/MarcoAcceso.vue'
import { useSesionStore } from '../stores/sesion'

// Cambio voluntario. El cambio obligatorio de la contraseña temporal ocurre en la bienvenida: la
// guarda de navegación no deja llegar aquí mientras quede un paso pendiente.
const router = useRouter()
const sesion = useSesionStore()

function irAlInicio(aviso?: string) {
  router.replace({ name: 'inicio', state: aviso ? { aviso } : undefined })
}

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}
</script>

<template>
  <MarcoAcceso>
    <h1 class="text-[24px] leading-tight font-extrabold tracking-[-0.03em]">
      Cambia tu contraseña.
    </h1>
    <p class="mt-2 mb-6 text-[13px] text-secundario">
      Al guardarla, se cerrarán tus otras sesiones abiertas.
    </p>
    <FormularioCambioContrasena
      :inicial="false"
      @cambiada="irAlInicio('Contraseña actualizada. Ya puedes usarla en tus próximos ingresos.')"
      @volver="irAlInicio()"
      @sesion-terminada="sesionTerminada"
    />
  </MarcoAcceso>
</template>
