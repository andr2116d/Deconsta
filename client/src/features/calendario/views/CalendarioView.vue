<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import type { ColorCategoria } from '@/features/categorias/types'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { listarPedidos } from '@/features/pagos/api/pagos'
import type { Pedido } from '@/features/pagos/types'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { consultarCalendario } from '../api/calendario'
import CuadriculaMes from '../components/CuadriculaMes.vue'
import PanelDia from '../components/PanelDia.vue'
import ProximosVencimientos from '../components/ProximosVencimientos.vue'
import ResumenMes from '../components/ResumenMes.vue'
import {
  esDia,
  esMes,
  hoyLocal,
  mesDe,
  nombreMes,
  semanasDelMes,
  sumarDias,
  sumarMeses,
} from '../fechas'
import type { Calendario, Dia, Mes, Vencimiento } from '../types'

const DIAS_PROXIMOS = 14

const route = useRoute()
const router = useRouter()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const notificaciones = useNotificacionesStore()

// Hasta que responda el backend, hoy es el día del navegador.
const hoyServidor = ref<Dia | null>(null)
const hoy = computed(() => hoyServidor.value ?? hoyLocal())

const pedidoMes = route.query.mes
const pedidoDia = route.query.dia
const mes = ref<Mes>(
  esMes(pedidoMes) ? pedidoMes : esDia(pedidoDia) ? mesDe(pedidoDia) : mesDe(hoy.value),
)
const seleccionado = ref<Dia>(
  esDia(pedidoDia) && mesDe(pedidoDia) === mes.value
    ? pedidoDia
    : mes.value === mesDe(hoy.value)
      ? hoy.value
      : `${mes.value}-01`,
)
// Para que la cuadrícula se deslice hacia el lado al que se avanza.
const direccion = ref<'adelante' | 'atras'>('adelante')
const marco = ref<HTMLElement | null>(null)
// Al cruzar de mes con el teclado, el foco sigue al día elegido en la cuadrícula nueva.
let enfocarAlEntrar = false

// Lo ya consultado de cada mes: volver a uno no hace esperar.
const meses = ref(new Map<Mes, Calendario>())
const proximos = ref<Vencimiento[] | null>(null)
const cargando = ref(false)
const fallo = ref<string | null>(null)
let consulta = 0

const semanas = computed(() => semanasDelMes(mes.value))
const actual = computed(() => meses.value.get(mes.value) ?? null)
const porDia = computed(() => {
  const mapa = new Map<Dia, Vencimiento[]>()
  for (const v of actual.value?.vencimientos ?? []) {
    mapa.set(v.vence_el, [...(mapa.get(v.vence_el) ?? []), v])
  }
  return mapa
})
const delDia = computed(() => porDia.value.get(seleccionado.value) ?? [])
const rol = computed(() => sesion.usuario?.rol ?? 'asistente')

// Los pedidos de pago pendientes: el gerente los ve y los retira desde el día.
const pedidos = ref<Pedido[]>([])
const pedidoDe = (deudaId: string, cuota: number) =>
  pedidos.value.find((p) => p.deuda_id === deudaId && p.cuota === cuota) ?? null

async function cargarPedidos() {
  if (rol.value !== 'gerente') return
  try {
    pedidos.value = await listarPedidos()
  } catch {
    // Sin la lista, el día solo ofrece pedir el pago; el backend avisa si ya se pidió.
  }
}

const categoriaDe = (id: string | null) => categorias.categorias?.find((c) => c.id === id) ?? null
const colorDe = (id: string | null): ColorCategoria => categoriaDe(id)?.color ?? 'grafito'

function tratar(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    sesion.olvidar()
    router.replace({ name: 'inicio-sesion' })
  } else {
    fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
  }
}

async function cargarMes(pedido: Mes) {
  if (meses.value.has(pedido)) return
  const dias = semanasDelMes(pedido).flat()
  const numero = ++consulta
  cargando.value = true
  fallo.value = null
  try {
    const calendario = await consultarCalendario(dias[0]!, dias[dias.length - 1]!)
    hoyServidor.value = calendario.hoy
    meses.value.set(pedido, calendario)
  } catch (error) {
    if (numero === consulta) tratar(error)
  } finally {
    if (numero === consulta) cargando.value = false
  }
}

async function cargarProximos() {
  try {
    const desde = hoy.value
    const calendario = await consultarCalendario(desde, sumarDias(desde, DIAS_PROXIMOS - 1))
    hoyServidor.value = calendario.hoy
    proximos.value = calendario.vencimientos.filter((v) => v.vence_el >= calendario.hoy)
  } catch (error) {
    // El calendario del mes ya informa del problema.
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') tratar(error)
  }
}

function recargar() {
  meses.value = new Map()
  void cargarMes(mes.value)
  void cargarProximos()
  void cargarPedidos()
}

function seleccionar(dia: Dia) {
  const destino = mesDe(dia)
  if (destino !== mes.value) {
    enfocarAlEntrar = marco.value?.contains(document.activeElement) ?? false
    direccion.value = destino > mes.value ? 'adelante' : 'atras'
    mes.value = destino
  }
  seleccionado.value = dia
}

function cambiarMes(salto: number) {
  const destino = sumarMeses(mes.value, salto)
  // Al llegar al mes de hoy se marca hoy; en otro mes, su primer día.
  seleccionar(destino === mesDe(hoy.value) ? hoy.value : `${destino}-01`)
}

const irAHoy = () => seleccionar(hoy.value)

function alEntrarMes() {
  if (!enfocarAlEntrar) return
  enfocarAlEntrar = false
  marco.value?.querySelector<HTMLElement>(`[data-dia="${seleccionado.value}"]`)?.focus()
}

watch(mes, (nuevo) => void cargarMes(nuevo))
// El mes y el día quedan en la dirección: se pueden compartir y sobreviven a una recarga.
watch([mes, seleccionado], () => {
  void router.replace({ query: { ...route.query, mes: mes.value, dia: seleccionado.value } })
})
// Una deuda nueva o una decisión del gerente llegan como aviso: el calendario se actualiza solo.
watch(() => notificaciones.avisos, recargar)

onMounted(() => {
  void cargarMes(mes.value)
  void cargarProximos()
  void cargarPedidos()
  if (!categorias.categorias) categorias.cargar().catch(() => undefined)
})
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Tu calendario de pagos.
        </h1>
        <p class="mt-2 max-w-[62ch] text-[13px] text-secundario">
          Cada cuota del espacio en el día que vence, hacia atrás y hacia adelante. Elige un día
          para ver qué vence.
        </p>
      </div>
      <RouterLink
        :to="{ name: 'registrar-deuda' }"
        class="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 self-start rounded-[9px] bg-acento px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover sm:self-auto"
      >
        <BaseIcono nombre="mas" class="size-[18px]" />
        Registrar deuda
      </RouterLink>
    </header>

    <ProximosVencimientos
      v-if="proximos"
      class="mb-6"
      :dias="DIAS_PROXIMOS"
      :hoy="hoy"
      :vencimientos="proximos"
      :color-de="colorDe"
      @seleccionar="seleccionar"
    />

    <BaseAviso v-if="fallo" tono="error" class="mb-6">
      {{ fallo }}
      <BaseBoton variante="discreto" class="ml-1 min-h-8! px-2!" @click="recargar">
        Volver a intentar
      </BaseBoton>
    </BaseAviso>

    <div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="flex min-w-0 flex-col gap-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-1">
            <h2 class="mr-2 min-w-[170px] text-[20px] font-extrabold tracking-[-0.02em]">
              {{ nombreMes(mes) }}
            </h2>
            <button
              type="button"
              aria-label="Mes anterior"
              class="grid size-9 place-items-center rounded-[9px] border border-borde bg-white transition-colors hover:bg-fondo"
              @click="cambiarMes(-1)"
            >
              <BaseIcono nombre="derecha" class="size-4 rotate-180" />
            </button>
            <button
              type="button"
              aria-label="Mes siguiente"
              class="grid size-9 place-items-center rounded-[9px] border border-borde bg-white transition-colors hover:bg-fondo"
              @click="cambiarMes(1)"
            >
              <BaseIcono nombre="derecha" class="size-4" />
            </button>
            <BaseBoton
              variante="secundario"
              class="ml-1 min-h-9!"
              :deshabilitado="seleccionado === hoy"
              @click="irAHoy"
            >
              Hoy
            </BaseBoton>
          </div>
          <p role="status" class="text-[12px] text-secundario">
            <span v-if="cargando" class="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                class="size-3.5 animate-girar rounded-full border-2 border-acento border-t-transparent"
              />
              Cargando los vencimientos…
            </span>
          </p>
        </div>

        <ResumenMes :mes="mes" :hoy="hoy" :vencimientos="actual?.vencimientos ?? []" />

        <div ref="marco" class="overflow-hidden rounded-2xl border border-borde bg-white">
          <Transition :name="`mes-${direccion}`" mode="out-in" @after-enter="alEntrarMes">
            <CuadriculaMes
              :key="mes"
              :semanas="semanas"
              :mes="mes"
              :hoy="hoy"
              :seleccionado="seleccionado"
              :por-dia="porDia"
              :color-de="colorDe"
              :class="cargando && !actual ? 'opacity-60' : ''"
              @seleccionar="seleccionar"
            />
          </Transition>
        </div>

        <ul class="flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-secundario">
          <li class="flex items-center gap-1.5">
            <i aria-hidden="true" class="h-[3px] w-4 rounded-full bg-error" />Vence hoy
          </li>
          <li class="flex items-center gap-1.5">
            <i aria-hidden="true" class="h-[3px] w-4 rounded-full bg-aviso" />En 3 días o menos
          </li>
          <li class="flex items-center gap-1.5">
            <i aria-hidden="true" class="h-[3px] w-4 rounded-full bg-acento/60" />Más adelante
          </li>
          <li class="flex items-center gap-1.5">
            <i aria-hidden="true" class="h-[3px] w-4 rounded-full bg-control/50" />Fecha pasada
          </li>
          <li class="flex items-center gap-1.5">
            <i
              aria-hidden="true"
              class="h-3 w-4 rounded-sm outline-1 outline-aviso outline-dashed"
            />
            Espera autorización
          </li>
          <li class="text-control">Usa las flechas del teclado para moverte entre los días.</li>
        </ul>
      </div>

      <PanelDia
        :dia="seleccionado"
        :hoy="hoy"
        :vencimientos="delDia"
        :rol="rol"
        :categoria-de="categoriaDe"
        :pedido-de="pedidoDe"
        @cambio="cargarPedidos"
      />
    </div>
  </section>
</template>

<style scoped>
.mes-adelante-enter-active,
.mes-adelante-leave-active,
.mes-atras-enter-active,
.mes-atras-leave-active {
  transition:
    opacity 200ms ease,
    transform 200ms ease;
}

.mes-adelante-enter-from,
.mes-atras-leave-to {
  opacity: 0;
  transform: translateX(16px);
}

.mes-adelante-leave-to,
.mes-atras-enter-from {
  opacity: 0;
  transform: translateX(-16px);
}
</style>
