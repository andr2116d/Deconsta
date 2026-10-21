<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, type RouteLocationRaw } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import { useNotificacionesStore } from '../stores/notificaciones'
import type { Notificacion } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const store = useNotificacionesStore()
const fallo = ref<string | null>(null)

const fecha = new Intl.DateTimeFormat('es-PE', {
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'America/Lima',
})

const ICONOS: Record<Notificacion['tipo'], NombreIcono> = {
  DEUDA_POR_AUTORIZAR: 'escudo',
  DEUDA_REGISTRADA: 'documento',
  REGISTRO_BLOQUEADO: 'alerta',
  DEUDA_AUTORIZADA: 'check',
  DEUDA_RECHAZADA: 'cerrar',
  DEUDA_ANULADA: 'cerrar',
  REGISTRO_DESBLOQUEADO: 'check',
}

/** El siguiente paso de cada aviso, según el rol. */
function destino(n: Notificacion): { etiqueta: string; ruta: RouteLocationRaw } | null {
  const gerente = sesion.usuario?.rol === 'gerente'
  if (gerente && n.deuda_id) {
    return {
      etiqueta: 'Revisar la deuda',
      ruta: { name: 'por-autorizar', query: { deuda: n.deuda_id } },
    }
  }
  if (gerente && n.tipo === 'REGISTRO_BLOQUEADO') {
    return { etiqueta: 'Ir a Mi equipo', ruta: { name: 'equipo' } }
  }
  if (n.tipo === 'REGISTRO_DESBLOQUEADO') {
    return { etiqueta: 'Registrar una deuda', ruta: { name: 'registrar-deuda' } }
  }
  return null
}

const lista = computed(() => store.notificaciones ?? [])

function tratar(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    sesion.olvidar()
    router.replace({ name: 'inicio-sesion' })
    return
  }
  fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
}

async function abrir(n: Notificacion) {
  const siguiente = destino(n)
  try {
    await store.marcarLeida(n.id)
  } catch (error) {
    tratar(error)
    return
  }
  if (siguiente) await router.push(siguiente.ruta)
}

async function marcarTodas() {
  try {
    await store.marcarTodas()
  } catch (error) {
    tratar(error)
  }
}

onMounted(() => store.cargar().catch(tratar))
</script>

<template>
  <section aria-labelledby="titulo-seccion" class="max-w-[900px]">
    <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Cada aviso, con su siguiente paso.
        </h1>
        <p class="mt-2 text-[13px] text-secundario">
          Se guardan en tu cuenta: siguen aquí aunque cierres sesión.
        </p>
      </div>
      <BaseBoton
        v-if="store.noLeidas"
        variante="secundario"
        class="self-start sm:self-auto"
        @click="marcarTodas"
      >
        Marcar todo como leído
      </BaseBoton>
    </header>

    <BaseAviso v-if="fallo" tono="error" class="mb-6">{{ fallo }}</BaseAviso>

    <div v-if="store.notificaciones === null && !fallo" class="flex justify-center py-16">
      <span
        aria-label="Cargando tus avisos"
        class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
      />
    </div>
    <p
      v-else-if="!lista.length"
      class="rounded-2xl border border-borde bg-white px-6 py-12 text-center text-[13px] text-secundario"
    >
      No tienes avisos todavía. Las deudas que esperan tu decisión y sus respuestas aparecerán aquí.
    </p>
    <TransitionGroup
      v-else
      tag="ul"
      name="vista"
      class="rounded-[14px] border border-borde bg-white"
    >
      <li
        v-for="n in lista"
        :key="n.id"
        class="grid grid-cols-[38px_1fr] gap-3 border-b border-borde px-4 py-5 last:border-b-0 sm:grid-cols-[44px_1fr_auto] sm:px-6"
      >
        <span
          aria-hidden="true"
          class="grid size-[38px] place-items-center rounded-full sm:size-11"
          :class="n.leida ? 'bg-fondo text-secundario' : 'bg-acento-suave text-acento'"
        >
          <BaseIcono :nombre="ICONOS[n.tipo]" class="size-[18px]" />
        </span>
        <div class="min-w-0">
          <h2 class="flex items-center gap-2 text-[13px] font-extrabold">
            {{ n.titulo }}
            <span v-if="!n.leida" class="size-1.5 rounded-full bg-acento" />
            <span v-if="!n.leida" class="sr-only">(sin leer)</span>
          </h2>
          <p class="mt-1 max-w-[590px] text-[12px] text-secundario">{{ n.cuerpo }}</p>
          <button
            v-if="destino(n) || !n.leida"
            type="button"
            class="mt-2 inline-flex items-center gap-1 text-[12px] font-bold text-acento hover:underline"
            @click="abrir(n)"
          >
            {{ destino(n)?.etiqueta ?? 'Marcar como leído' }}
            <BaseIcono v-if="destino(n)" nombre="derecha" class="size-3.5" />
          </button>
        </div>
        <time
          :datetime="n.creada_en"
          class="col-start-2 text-[11px] text-secundario sm:col-start-3"
        >
          {{ fecha.format(new Date(n.creada_en)) }}
        </time>
      </li>
    </TransitionGroup>
  </section>
</template>
