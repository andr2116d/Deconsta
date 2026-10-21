<script setup lang="ts">
import { useRouter } from 'vue-router'

import FormularioIngreso from '../components/FormularioIngreso.vue'
import MarcoAcceso from '../components/MarcoAcceso.vue'
import type { Ingreso } from '../types'

const router = useRouter()

function continuar(ingreso: Ingreso) {
  // Mientras quede un paso del primer ingreso, cada ingreso pasa primero por la bienvenida.
  router.replace({ name: ingreso.pasos_pendientes.length ? 'incorporacion' : 'inicio' })
}
</script>

<template>
  <MarcoAcceso>
    <h1 class="text-[24px] leading-tight font-extrabold tracking-[-0.03em]">Entra a tu espacio.</h1>
    <p class="mt-2 mb-6 text-[13px] text-secundario">
      Usa el usuario y la contraseña que te entregaron. Tu rol define lo que verás al ingresar.
    </p>
    <FormularioIngreso @ingreso="continuar" />
  </MarcoAcceso>
</template>
