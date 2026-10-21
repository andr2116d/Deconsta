<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'

import FormularioDatosPersonales from '../components/FormularioDatosPersonales.vue'
import TarjetaCuenta from '../components/TarjetaCuenta.vue'
import { useCuentaStore } from '../stores/cuenta'

const router = useRouter()
const sesion = useSesionStore()
const cuenta = useCuentaStore()

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}
</script>

<template>
  <TarjetaCuenta
    titulo="Datos personales"
    descripcion="Esta información aparece junto a tus registros y decisiones."
    :cargando="!cuenta.cuenta"
  >
    <FormularioDatosPersonales
      v-if="cuenta.cuenta"
      :cuenta="cuenta.cuenta"
      @sesion-terminada="sesionTerminada"
    />
  </TarjetaCuenta>
</template>
