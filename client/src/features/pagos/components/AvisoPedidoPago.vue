<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { formatearFecha } from '@/features/deudas/catalogo'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { listarPedidos } from '../api/pagos'
import type { Pedido } from '../types'

/**
 * Los pagos que el gerente pidió a esta asistente. Al entrar sale un aviso a pantalla completa; si
 * lo deja para después, queda una barra arriba y el aviso vuelve a los 30 minutos, o antes si
 * llega un pedido nuevo. Desaparece cuando la cuota tiene un pago o el gerente retira el pedido.
 */
const POSPONER_MS = 30 * 60 * 1000
const CLAVE = 'deconsta:pedidos-pospuestos'

interface Pospuesto {
  hasta: number
  ids: string[]
}

const route = useRoute()
const router = useRouter()
const sesion = useSesionStore()
const notificaciones = useNotificacionesStore()

const pedidos = ref<Pedido[]>([])
const ahora = ref(Date.now())
const pospuesto = ref<Pospuesto | null>(leer())
const dialogo = ref<HTMLDialogElement>()
let temporizador: ReturnType<typeof setTimeout> | undefined

// La marca vive en la pestaña: una recarga no vuelve a mostrar el aviso antes de tiempo, pero un
// ingreso nuevo sí. Sin sessionStorage (modo privado estricto), queda solo en memoria.
function leer(): Pospuesto | null {
  try {
    const valor = JSON.parse(sessionStorage.getItem(CLAVE) ?? 'null') as Pospuesto | null
    return valor && typeof valor.hasta === 'number' && Array.isArray(valor.ids) ? valor : null
  } catch {
    return null
  }
}

function guardar(valor: Pospuesto) {
  pospuesto.value = valor
  try {
    sessionStorage.setItem(CLAVE, JSON.stringify(valor))
  } catch {
    // Solo en memoria.
  }
}

const primero = computed(() => pedidos.value[0] ?? null)
// En la pantalla de registrar el pago el aviso estorbaría: ya está atendiendo un pedido.
const registrando = computed(() => route.name === 'registrar-pago')
const abierto = computed(() => {
  if (!primero.value || registrando.value) return false
  const p = pospuesto.value
  if (!p || ahora.value >= p.hasta) return true
  // Un pedido nuevo no espera a que pase el plazo.
  return pedidos.value.some((pedido) => !p.ids.includes(pedido.id))
})
const nombre = computed(() => sesion.usuario?.nombres.split(' ')[0] ?? '')

async function cargar() {
  try {
    pedidos.value = await listarPedidos()
  } catch {
    // Sin conexión no se interrumpe a la asistente; se intenta con el siguiente aviso.
  }
}

function programar() {
  clearTimeout(temporizador)
  const p = pospuesto.value
  if (!p || p.hasta <= Date.now()) return
  temporizador = setTimeout(() => (ahora.value = Date.now()), p.hasta - Date.now())
}

function posponer() {
  ahora.value = Date.now()
  guardar({ hasta: ahora.value + POSPONER_MS, ids: pedidos.value.map((p) => p.id) })
  programar()
}

function registrar() {
  const pedido = primero.value
  if (!pedido) return
  posponer()
  void router.push({
    name: 'registrar-pago',
    query: { deuda: pedido.deuda_id, cuota: pedido.cuota },
  })
}

function sincronizar() {
  const elemento = dialogo.value
  if (!elemento) return
  if (abierto.value && !elemento.open) {
    // jsdom no implementa showModal; en el navegador siempre existe.
    if (typeof elemento.showModal === 'function') elemento.showModal()
    else elemento.setAttribute('open', '')
  } else if (!abierto.value && elemento.open) {
    cerrar(elemento)
  }
}

function cerrar(elemento: HTMLDialogElement) {
  if (typeof elemento.close === 'function') elemento.close()
  else elemento.removeAttribute('open')
}

// Escape equivale a «Ver después».
function alCancelar(evento: Event) {
  evento.preventDefault()
  posponer()
}

watch(abierto, sincronizar, { flush: 'post' })
watch(() => notificaciones.avisos, cargar)
onMounted(() => {
  void cargar()
  programar()
})
onBeforeUnmount(() => {
  clearTimeout(temporizador)
  if (dialogo.value?.open) cerrar(dialogo.value)
})
</script>

<template>
  <div
    v-if="primero && !abierto"
    role="region"
    aria-label="Pagos que te pidió tu gerente"
    class="border-b border-aviso/30 bg-aviso-fondo"
  >
    <div
      class="mx-auto flex w-full max-w-[1440px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-[12px] sm:px-6 lg:px-10"
    >
      <BaseIcono nombre="reloj" class="size-4 shrink-0 text-aviso" />
      <p class="min-w-0 flex-1 font-bold text-tinta">
        <template v-if="pedidos.length === 1">
          Tu gerente te pidió pagar «{{ primero.concepto }}».
        </template>
        <template v-else>Tu gerente te pidió pagar {{ pedidos.length }} deudas.</template>
      </p>
      <RouterLink
        :to="
          pedidos.length === 1
            ? { name: 'registrar-pago', query: { deuda: primero.deuda_id, cuota: primero.cuota } }
            : { name: 'pagos-por-completar' }
        "
        class="font-bold text-acento hover:underline"
      >
        {{ pedidos.length === 1 ? 'Registrar pago' : 'Ver los pagos' }}
      </RouterLink>
    </div>
  </div>

  <dialog
    ref="dialogo"
    aria-labelledby="titulo-pedido-pago"
    aria-describedby="detalle-pedido-pago"
    class="m-0 h-dvh max-h-none w-full max-w-none bg-white p-0 text-tinta motion-safe:open:animate-aparecer"
    @cancel="alCancelar"
  >
    <div
      v-if="primero"
      class="mx-auto flex min-h-full max-w-[560px] flex-col justify-center px-6 py-10"
    >
      <span
        aria-hidden="true"
        class="grid size-14 place-items-center rounded-[16px] bg-aviso-fondo text-aviso"
      >
        <BaseIcono nombre="reloj" class="size-7" />
      </span>
      <h2
        id="titulo-pedido-pago"
        class="mt-6 text-[28px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[34px]"
      >
        Este pago necesita tu atención<template v-if="nombre">, {{ nombre }}</template
        >.
      </h2>
      <p id="detalle-pedido-pago" class="mt-3 text-[14px] text-secundario">
        Tu gerente te pidió pagar <strong class="text-tinta">{{ primero.concepto }}</strong
        ><template v-if="primero.cuotas > 1">
          (cuota {{ primero.cuota }} de {{ primero.cuotas }})</template
        >.
        <template v-if="!primero.nota">
          Registra el comprobante cuando completes la operación.
        </template>
      </p>
      <blockquote
        v-if="primero.nota"
        class="mt-4 rounded-[10px] border-l-4 border-aviso bg-fondo px-4 py-3 text-[14px]"
      >
        «{{ primero.nota }}»
      </blockquote>
      <dl class="mt-6 divide-y divide-borde rounded-[12px] border border-borde">
        <div class="flex items-center justify-between px-4 py-3 text-[13px]">
          <dt class="text-secundario">Importe</dt>
          <dd class="text-[18px] font-extrabold">{{ formatearSoles(primero.importe) }}</dd>
        </div>
        <div class="flex items-center justify-between px-4 py-3 text-[13px]">
          <dt class="text-secundario">Vencimiento</dt>
          <dd class="font-bold" :class="primero.vencida_hace !== null ? 'text-error' : ''">
            {{ formatearFecha(primero.vence_el) }}
            <template v-if="primero.vencida_hace !== null">
              · vencida hace {{ primero.vencida_hace }}
              {{ primero.vencida_hace === 1 ? 'día' : 'días' }}
            </template>
          </dd>
        </div>
      </dl>
      <p v-if="pedidos.length > 1" class="mt-3 text-[12px] text-secundario">
        Y {{ pedidos.length - 1 }} pago{{ pedidos.length > 2 ? 's' : '' }} más que te pidió.
      </p>
      <p class="mt-6 text-[12px] text-secundario">
        Este aviso volverá mientras el pago siga pendiente. Puedes seguir con lo demás.
      </p>
      <div class="mt-4 flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[9px] bg-acento px-5 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover"
          @click="registrar"
        >
          Registrar pago
          <BaseIcono nombre="derecha" class="size-4" />
        </button>
        <button
          type="button"
          class="inline-flex min-h-11 items-center justify-center rounded-[9px] px-5 text-[13px] font-bold text-acento transition-colors duration-200 hover:bg-acento-suave"
          @click="posponer"
        >
          Ver después
        </button>
      </div>
    </div>
  </dialog>
</template>
