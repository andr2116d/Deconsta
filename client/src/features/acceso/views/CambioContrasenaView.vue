<script setup lang="ts">
import { useRouter } from 'vue-router'

import FormularioCambioContrasena from '../components/FormularioCambioContrasena.vue'
import MarcoAcceso from '../components/MarcoAcceso.vue'
import { useSesionStore } from '../stores/sesion'

const router = useRouter()
const sesion = useSesionStore()
// Se fija al abrir la vista: tras guardar, el indicador cambia pero el texto no debe saltar.
const inicial = sesion.debeCambiarContrasena

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
    <p
      v-if="inicial"
      class="mb-3 inline-flex rounded-full bg-rosa px-2.5 py-1 text-[11px] font-bold text-ciruela"
    >
      Primer paso de seguridad
    </p>
    <h1 class="text-[24px] leading-tight font-extrabold tracking-[-0.03em]">
      {{ inicial ? 'Crea tu contraseña personal.' : 'Cambia tu contraseña.' }}
    </h1>
    <p class="mt-2 mb-6 text-[13px] text-secundario">
      <template v-if="inicial">
        Ingresaste con una contraseña temporal. Cámbiala ahora para proteger tu cuenta; si lo dejas
        para después, te lo recordaremos en cada ingreso.
      </template>
      <template v-else>Al guardarla, se cerrarán tus otras sesiones abiertas.</template>
    </p>
    <FormularioCambioContrasena
      :inicial="inicial"
      @cambiada="irAlInicio('Contraseña actualizada. Ya puedes usarla en tus próximos ingresos.')"
      @omitir="irAlInicio()"
      @sesion-terminada="sesionTerminada"
    />
  </MarcoAcceso>
</template>
