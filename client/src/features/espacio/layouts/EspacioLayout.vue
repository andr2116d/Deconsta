<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { obtenerEspacio } from '@/features/incorporacion/api/incorporacion'
import ModalCambioContrasena from '@/features/incorporacion/components/ModalCambioContrasena.vue'
import AvisoEnVivo from '@/features/notificaciones/components/AvisoEnVivo.vue'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'

import CabeceraEspacio from '../components/CabeceraEspacio.vue'

const router = useRouter()
const route = useRoute()
const sesion = useSesionStore()
const notificaciones = useNotificacionesStore()
const saliendo = ref(false)
// Aviso que deja la pantalla anterior (por ejemplo, al terminar la bienvenida).
const aviso = ref(typeof history.state?.aviso === 'string' ? (history.state.aviso as string) : null)
const contrasenaPedida = ref(false)

// La ventana aparece sola en cada ingreso mientras la contraseña siga siendo temporal; desde el
// menú de la cuenta se puede volver a abrir aunque se haya pospuesto.
const mostrarContrasena = computed(
  () => sesion.debeCambiarContrasena && (sesion.recordarContrasena || contrasenaPedida.value),
)

function posponerContrasena() {
  contrasenaPedida.value = false
  sesion.posponerCambioContrasena()
}

// Se deduce del cambio de estado y no de un evento de la ventana: al guardar, la sesión se
// actualiza y la ventana se desmonta antes de poder avisar. Si el cambio se hizo desde
// «Mi cuenta», esa pantalla ya lo confirma.
watch(mostrarContrasena, (mostrar, mostraba) => {
  if (!mostraba || mostrar || sesion.debeCambiarContrasena || !sesion.autenticada) return
  contrasenaPedida.value = false
  aviso.value = 'Contraseña actualizada. Ya puedes usarla en tus próximos ingresos.'
})

function irAlIngreso() {
  router.replace({ name: 'inicio-sesion' })
}

function sesionTerminada() {
  sesion.olvidar()
  irAlIngreso()
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

// Al cambiar de sección, el foco pasa al título nuevo para que el lector de pantalla lo anuncie.
let navegado = false
watch(
  () => route.name,
  () => {
    navegado = true
    aviso.value = null
  },
)

function enfocarTitulo() {
  // Si durante la transición la persona abrió el menú de la cuenta, el foco se queda con ella.
  if (!navegado || document.activeElement?.closest('[data-menu-abierto]')) return
  document.getElementById('titulo-seccion')?.focus({ preventScroll: true })
}

// La guarda decide con la sesión del navegador; el backend confirma que la cuenta puede entrar.
// Si se publicó otra versión de los documentos o la sesión dejó de valer, se vuelve al paso que
// corresponda.
onMounted(async () => {
  try {
    await obtenerEspacio()
    // Avisos de la cuenta: los guardados y, en adelante, los que lleguen en tiempo real.
    notificaciones.cargar().catch(() => undefined)
    notificaciones.conectar()
  } catch (error) {
    if (!(error instanceof ErrorApi)) return
    if (error.codigo === 'NO_AUTENTICADO') {
      sesionTerminada()
    } else if (error.codigo === 'INCORPORACION_PENDIENTE') {
      await sesion.recargar().catch(() => undefined)
      router.replace({ name: 'incorporacion' })
    }
  }
})
// Al salir del espacio (cerrar sesión o sesión vencida) se corta el flujo y se olvidan los avisos.
onBeforeUnmount(() => notificaciones.olvidar())
</script>

<template>
  <div v-if="sesion.usuario" class="flex min-h-dvh flex-col">
    <a
      href="#contenido"
      class="sr-only z-50 rounded-lg bg-acento px-4 py-2 text-[13px] font-bold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      Saltar al contenido
    </a>
    <CabeceraEspacio
      :usuario="sesion.usuario"
      :contrasena-temporal="sesion.debeCambiarContrasena"
      :saliendo="saliendo"
      @cambiar-contrasena="contrasenaPedida = true"
      @salir="salir"
    />

    <main
      id="contenido"
      tabindex="-1"
      class="mx-auto w-full max-w-[1440px] flex-1 min-[1920px]:max-w-[1680px] px-4 pt-6 pb-16 focus:outline-none sm:px-6 lg:px-10 lg:pt-8"
    >
      <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>
      <RouterView v-slot="{ Component, route: actual }">
        <Transition name="vista" mode="out-in" @after-enter="enfocarTitulo">
          <!-- Las pestañas de «Mi cuenta» comparten marco: la clave es la ruta de primer nivel. -->
          <component :is="Component" :key="actual.matched[1]?.path ?? actual.name" />
        </Transition>
      </RouterView>
    </main>

    <AvisoEnVivo />

    <ModalCambioContrasena
      v-if="mostrarContrasena"
      @cerrar="posponerContrasena"
      @sesion-terminada="sesionTerminada"
    />
  </div>
</template>
