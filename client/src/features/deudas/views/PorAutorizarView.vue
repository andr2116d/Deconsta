<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { consultarDeuda, listarPendientes } from '../api/deudas'
import { formatearFecha, MOTIVOS } from '../catalogo'
import DetalleDecision from '../components/DetalleDecision.vue'
import type { Deuda, DeudaDetalle } from '../types'

const router = useRouter()
const route = useRoute()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const notificaciones = useNotificacionesStore()

const pendientes = ref<Deuda[] | null>(null)
const elegida = ref<DeudaDetalle | null>(null)
const cargandoDetalle = ref(false)
const fallo = ref<string | null>(null)
const aviso = ref<string | null>(null)

const nombreCategoria = (id: string | null) =>
  categorias.categorias?.find((c) => c.id === id)?.nombre ?? null

const porAutorizar = computed(
  () => pendientes.value?.filter((d) => d.estado === 'por_autorizar') ?? [],
)
const enRevision = computed(
  () => pendientes.value?.filter((d) => d.estado !== 'por_autorizar') ?? [],
)

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

function tratar(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  else fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
}

async function abrir(id: string) {
  if (elegida.value?.id === id) return
  cargandoDetalle.value = true
  try {
    elegida.value = await consultarDeuda(id)
  } catch (error) {
    tratar(error)
  } finally {
    cargandoDetalle.value = false
  }
}

async function cargar() {
  fallo.value = null
  try {
    pendientes.value = await listarPendientes()
  } catch (error) {
    tratar(error)
    return
  }
  const pedida = typeof route.query.deuda === 'string' ? route.query.deuda : null
  const sigue = pendientes.value.find((d) => d.id === (pedida ?? elegida.value?.id))
  const primera = sigue ?? pendientes.value[0]
  if (primera) await abrir(primera.id)
  else elegida.value = null
}

async function alDecidir(_: DeudaDetalle, mensaje: string) {
  aviso.value = mensaje
  elegida.value = null
  if (route.query.deuda) await router.replace({ query: {} })
  await cargar()
}

// Una deuda nueva de la asistente aparece al momento, sin recargar.
watch(() => notificaciones.avisos, cargar)

onMounted(() => {
  void cargar()
  if (!categorias.categorias) categorias.cargar().catch(() => undefined)
})
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      Lo que espera tu decisión.
    </h1>
    <p class="mt-2 mb-6 max-w-[62ch] text-[13px] text-secundario sm:mb-8">
      Lo que supera tu límite, tiene otro titular o un documento por revisar no se paga hasta que lo
      autorices. Lo demás ya se puede pagar: dale tu visto bueno o anúlalo si no corresponde.
    </p>

    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>
    <BaseAviso v-if="fallo" tono="error" class="mb-6">
      {{ fallo }}
    </BaseAviso>

    <div v-if="pendientes === null && !fallo" class="flex justify-center py-16">
      <span
        aria-label="Cargando tus pendientes"
        class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
      />
    </div>

    <div
      v-else-if="pendientes && !pendientes.length"
      class="mx-auto max-w-[520px] animate-aparecer rounded-2xl border border-borde bg-white px-6 py-12 text-center"
    >
      <span
        aria-hidden="true"
        class="mx-auto mb-4 grid size-14 place-items-center rounded-full bg-exito-fondo text-exito"
      >
        <BaseIcono nombre="check" class="size-7" />
      </span>
      <h2 class="text-[20px] font-extrabold">Todas tus decisiones están al día.</h2>
      <p class="mt-2 text-[13px] text-secundario">
        Cuando tu asistente registre una deuda, te llegará un aviso y aparecerá aquí.
      </p>
    </div>

    <div v-else-if="pendientes" class="grid items-start gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
      <nav aria-label="Deudas pendientes" class="flex flex-col gap-5 lg:sticky lg:top-[156px]">
        <div
          v-for="grupo in [
            { titulo: 'Esperan tu autorización', lista: porAutorizar },
            { titulo: 'Para tu visto bueno', lista: enRevision },
          ]"
          v-show="grupo.lista.length"
          :key="grupo.titulo"
        >
          <h2 class="mb-2 text-[12px] font-bold text-secundario">
            {{ grupo.titulo }} · {{ grupo.lista.length }}
          </h2>
          <ul class="flex flex-col gap-2">
            <li v-for="deuda in grupo.lista" :key="deuda.id">
              <button
                type="button"
                class="w-full rounded-[12px] border bg-white p-3.5 text-left transition-[border-color,box-shadow] duration-200 hover:shadow-[0_8px_26px_#30233012]"
                :class="elegida?.id === deuda.id ? 'border-acento' : 'border-borde'"
                :aria-current="elegida?.id === deuda.id ? 'true' : undefined"
                @click="abrir(deuda.id)"
              >
                <span class="flex items-start justify-between gap-3">
                  <strong class="text-[13px] leading-snug">{{ deuda.concepto }}</strong>
                  <span class="shrink-0 text-[13px] font-extrabold">
                    {{ formatearSoles(deuda.importe) }}
                  </span>
                </span>
                <small class="mt-1 block text-[11px] text-secundario">
                  {{ deuda.registrada_por.nombre }} · vence {{ formatearFecha(deuda.vence_el) }}
                </small>
                <span v-if="deuda.motivos.length" class="mt-2 flex flex-wrap gap-1">
                  <span
                    v-for="m in deuda.motivos"
                    :key="m"
                    class="rounded-full bg-aviso-fondo px-2 py-0.5 text-[10px] font-bold text-aviso"
                  >
                    {{ MOTIVOS[m] }}
                  </span>
                </span>
              </button>
            </li>
          </ul>
        </div>
      </nav>

      <div class="min-w-0">
        <div v-if="cargandoDetalle && !elegida" class="flex justify-center py-16">
          <span
            aria-label="Cargando la deuda"
            class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
          />
        </div>
        <DetalleDecision
          v-else-if="elegida"
          :key="elegida.id"
          :deuda="elegida"
          :categoria="nombreCategoria(elegida.categoria_id)"
          @decidida="alDecidir"
          @sesion-terminada="sesionTerminada"
        />
        <BaseBoton v-else variante="secundario" @click="cargar">Volver a cargar</BaseBoton>
      </div>
    </div>
  </section>
</template>
