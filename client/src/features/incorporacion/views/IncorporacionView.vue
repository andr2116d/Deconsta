<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import type { Sesion } from '@/features/acceso/types'
import MarcaDeconsta from '@/shared/components/MarcaDeconsta.vue'

import PasoPrivacidad from '../components/PasoPrivacidad.vue'
import PasosIncorporacion from '../components/PasosIncorporacion.vue'

// El paso que se muestra sale de la sesión que devuelve el backend, nunca de la navegación.
const router = useRouter()
const sesion = useSesionStore()
const saliendo = ref(false)

function irAlIngreso() {
  router.replace({ name: 'inicio-sesion' })
}

function sesionTerminada() {
  sesion.olvidar()
  irAlIngreso()
}

// Sin pasos pendientes, la cuenta ya puede entrar a su espacio.
watch(
  () => sesion.autenticada && sesion.pasoActual === null,
  (completa) => {
    if (!completa) return
    router.replace({
      name: 'inicio',
      state: { aviso: 'Todo listo. Tus autorizaciones quedaron registradas.' },
    })
  },
)

function alAceptar(nueva: Sesion) {
  sesion.actualizar(nueva)
}

async function recargar() {
  try {
    await sesion.recargar()
  } catch {
    // Sin conexión: se queda en el paso actual y el formulario permite reintentar.
    return
  }
  if (!sesion.autenticada) irAlIngreso()
}

async function salir() {
  saliendo.value = true
  try {
    await sesion.salir()
  } finally {
    saliendo.value = false
    irAlIngreso()
  }
}
</script>

<template>
  <div class="min-h-dvh bg-fondo">
    <main class="mx-auto w-full max-w-[900px] px-4 pt-6 pb-16 sm:px-9 sm:pt-8">
      <MarcaDeconsta />
      <template v-if="sesion.usuario">
        <PasosIncorporacion
          :usuario="sesion.usuario"
          :paso-actual="sesion.pasoActual"
          class="mt-8 mb-6"
        />
        <PasoPrivacidad
          v-if="sesion.pasoActual === 'aceptar_documentos'"
          :usuario="sesion.usuario"
          :saliendo="saliendo"
          @aceptada="alAceptar"
          @salir="salir"
          @recargar="recargar"
          @sesion-terminada="sesionTerminada"
        />
      </template>
    </main>
  </div>
</template>
