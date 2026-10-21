<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
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
          class="grid size-9 place-items-center rounded-full text-[13px] font-extrabold"
          :class="
            usuario?.rol === 'gerente' ? 'bg-rosa text-ciruela' : 'bg-[#e0eae3] text-[#365c4b]'
          "
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

        <p class="text-[13px] font-bold text-ciruela">Hola, {{ usuario?.nombres }}</p>
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

        <div class="mt-8 flex flex-col gap-3">
          <BaseAviso v-if="aviso" tono="exito">{{ aviso }}</BaseAviso>
          <BaseAviso v-if="sesion.debeCambiarContrasena" tono="aviso" titulo="Contraseña temporal">
            Tu cuenta todavía usa la contraseña que te entregaron. Cámbiala para protegerla.
            <RouterLink
              :to="{ name: 'cambio-contrasena' }"
              class="mt-2 block font-bold underline underline-offset-2"
            >
              Cambiar contraseña
            </RouterLink>
          </BaseAviso>
        </div>
      </div>
    </main>
  </div>
</template>
