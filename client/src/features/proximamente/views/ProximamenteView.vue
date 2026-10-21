<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { obtenerEspacio } from '@/features/incorporacion/api/incorporacion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import MarcaDeconsta from '@/shared/components/MarcaDeconsta.vue'

const router = useRouter()
const sesion = useSesionStore()
const saliendo = ref(false)
const aviso = typeof history.state?.aviso === 'string' ? (history.state.aviso as string) : null

const usuario = computed(() => sesion.usuario)
const iniciales = computed(() => usuario.value?.nombres.slice(0, 1).toUpperCase() ?? '')
const responsabilidad = computed(() =>
  usuario.value?.rol === 'gerente'
    ? 'Gerente · autoriza y supervisa'
    : 'Asistente · registra y completa pagos',
)

const proximos = ['Obligaciones', 'Calendario', 'Comprobantes', 'Historial']

// La guarda decide con la sesión del navegador; el backend confirma que la cuenta puede entrar.
// Si se publicó otra versión de los documentos o la sesión dejó de valer, se vuelve al paso que
// corresponda.
onMounted(async () => {
  try {
    await obtenerEspacio()
  } catch (error) {
    if (!(error instanceof ErrorApi)) return
    if (error.codigo === 'NO_AUTENTICADO') {
      sesion.olvidar()
      router.replace({ name: 'inicio-sesion' })
    } else if (error.codigo === 'INCORPORACION_PENDIENTE') {
      await sesion.recargar().catch(() => undefined)
      router.replace({ name: 'incorporacion' })
    }
  }
})

async function salir() {
  saliendo.value = true
  try {
    await sesion.salir()
  } finally {
    saliendo.value = false
    router.replace({ name: 'inicio-sesion' })
  }
}
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <header
      class="flex items-center justify-between gap-4 border-b border-borde bg-white px-4 py-3 sm:px-8"
    >
      <MarcaDeconsta />
      <div class="flex items-center gap-3">
        <div class="hidden text-right sm:block">
          <p class="text-[13px] leading-tight font-bold">{{ usuario?.nombres }}</p>
          <p class="text-[11px] text-secundario">{{ responsabilidad }}</p>
        </div>
        <span
          aria-hidden="true"
          class="grid size-9 place-items-center rounded-full bg-acento-suave text-[13px] font-extrabold text-acento"
        >
          {{ iniciales }}
        </span>
        <BaseBoton variante="secundario" :cargando="saliendo" @click="salir">
          Cerrar sesión
        </BaseBoton>
      </div>
    </header>

    <main class="mx-auto flex w-full max-w-[640px] flex-1 flex-col justify-center px-4 py-12">
      <div class="animate-aparecer">
        <div
          aria-hidden="true"
          class="mb-8 grid size-20 place-items-center rounded-3xl bg-rosa motion-safe:animate-flotar"
        >
          <span class="inline-flex -rotate-[25deg] gap-1.5">
            <i class="block h-10 w-2.5 rounded-full bg-ciruela" />
            <i class="mt-3.5 block h-6 w-2.5 rounded-full bg-ciruela/60" />
          </span>
        </div>

        <p class="text-[13px] font-bold text-acento">Hola, {{ usuario?.nombres }}</p>
        <h1
          class="mt-2 text-[32px] leading-[1.15] font-extrabold tracking-[-0.04em] sm:text-[40px]"
        >
          Estaremos disponibles pronto.
        </h1>
        <p class="mt-4 max-w-[52ch] text-[15px] text-secundario">
          Tu acceso ya funciona. Estamos terminando tu espacio de pagos, con todo y mejoras, para
          que registres, autorices y compruebes cada pago en un mismo lugar.
        </p>

        <ul class="mt-6 flex flex-wrap gap-2" aria-label="Lo que llega pronto">
          <li
            v-for="modulo in proximos"
            :key="modulo"
            class="rounded-full border border-borde bg-white px-3 py-1 text-[12px] font-bold text-secundario"
          >
            {{ modulo }}
          </li>
        </ul>

        <BaseAviso v-if="aviso" tono="exito" class="mt-8">{{ aviso }}</BaseAviso>
      </div>
    </main>
  </div>
</template>
