<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { partesDia } from '@/features/calendario/fechas'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { consultarPanel } from '../api/panel'
import JornadaAsistente from '../components/JornadaAsistente.vue'
import ResumenGerente from '../components/ResumenGerente.vue'
import type { Panel } from '../types'

/** El inicio del espacio: «Resumen» del gerente o «Mi jornada» de la asistente. */
const router = useRouter()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const notificaciones = useNotificacionesStore()

const panel = ref<Panel | null>(null)
const cargando = ref(false)
const fallo = ref(false)

const fecha = computed(() => {
  if (!panel.value) return ''
  const { semana, fecha } = partesDia(panel.value.hoy)
  return `${semana} ${fecha}`
})
const nombre = computed(() => sesion.usuario?.nombres.split(' ')[0] ?? '')
const categoriaDe = (id: string | null) =>
  categorias.categorias?.find((c) => c.id === id) ?? undefined

async function cargar() {
  cargando.value = true
  fallo.value = false
  try {
    panel.value = await consultarPanel()
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      sesion.olvidar()
      void router.replace({ name: 'inicio-sesion' })
      return
    }
    fallo.value = true
  } finally {
    cargando.value = false
  }
}

onMounted(() => {
  void cargar()
  if (!categorias.categorias) categorias.cargar().catch(() => undefined)
})
// Un aviso nuevo (un pago registrado, una decisión) cambia las cifras.
watch(
  () => notificaciones.avisos,
  () => void cargar(),
)
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-3 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-[13px] font-bold text-secundario">{{ fecha }}</p>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          {{
            sesion.usuario?.rol === 'gerente'
              ? 'Lo que necesita tu decisión.'
              : `${nombre}, esto sigue en tu jornada.`
          }}
        </h1>
      </div>
      <RouterLink
        v-if="sesion.usuario?.rol === 'gerente'"
        :to="{ name: 'historial' }"
        class="inline-flex items-center gap-1 text-[13px] font-bold text-acento hover:underline"
      >
        Ver todos los movimientos
        <BaseIcono nombre="derecha" class="size-4" />
      </RouterLink>
      <RouterLink
        v-else
        :to="{ name: 'registrar-deuda' }"
        class="inline-flex min-h-11 items-center gap-2 self-start rounded-[9px] bg-acento px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover sm:self-auto"
      >
        <BaseIcono nombre="mas" class="size-4" />
        Registrar una deuda
      </RouterLink>
    </header>

    <div v-if="fallo && !panel" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" titulo="No pudimos cargar tu inicio" class="w-full">
        Revisa tu conexión y vuelve a intentarlo.
      </BaseAviso>
      <BaseBoton variante="secundario" :cargando="cargando" @click="cargar">
        Volver a intentar
      </BaseBoton>
    </div>

    <div
      v-else-if="!panel"
      aria-hidden="true"
      class="flex flex-col gap-4 motion-safe:animate-pulse"
    >
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div v-for="n in 4" :key="n" class="h-[96px] rounded-[14px] border border-borde bg-white" />
      </div>
      <div class="h-[220px] rounded-[16px] border border-borde bg-white" />
    </div>

    <ResumenGerente
      v-else-if="panel.resumen"
      :resumen="panel.resumen"
      :hoy="panel.hoy"
      :categoria-de="categoriaDe"
      @cambio="cargar"
    />
    <JornadaAsistente
      v-else-if="panel.jornada"
      :jornada="panel.jornada"
      :hoy="panel.hoy"
      :categoria-de="categoriaDe"
    />
  </section>
</template>
