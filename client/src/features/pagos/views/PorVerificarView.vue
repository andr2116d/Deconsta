<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { formatearFecha } from '@/features/deudas/catalogo'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { consultarMora, consultarPago, listarMoras, listarPagos } from '../api/pagos'
import DetalleMora from '../components/DetalleMora.vue'
import DetallePago from '../components/DetallePago.vue'
import type { Mora, MoraDetalle, Pago, PagoDetalle } from '../types'

/**
 * Lo que las asistentes dejaron para el gerente en los pagos: las moras que esperan su aprobación
 * (la cuota no se paga mientras tanto) y los pagos que esperan su verificación.
 */
const router = useRouter()
const route = useRoute()
const sesion = useSesionStore()
const notificaciones = useNotificacionesStore()

const pendientes = ref<Pago[] | null>(null)
const moras = ref<Mora[]>([])
type Elegido = { tipo: 'pago'; pago: PagoDetalle } | { tipo: 'mora'; mora: MoraDetalle }
const elegido = ref<Elegido | null>(null)
const idElegido = () =>
  elegido.value?.tipo === 'pago' ? elegido.value.pago.id : elegido.value?.mora.id
const fallo = ref<string | null>(null)
const aviso = ref<string | null>(null)

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

function tratar(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  else fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
}

async function abrir(tipo: 'pago' | 'mora', id: string) {
  if (idElegido() === id) return
  try {
    elegido.value =
      tipo === 'pago'
        ? { tipo, pago: await consultarPago(id) }
        : { tipo, mora: await consultarMora(id) }
  } catch (error) {
    tratar(error)
  }
}

async function cargar() {
  fallo.value = null
  try {
    const [pagos, porAprobar] = await Promise.all([
      listarPagos('por_verificar'),
      listarMoras('por_aprobar'),
    ])
    pendientes.value = pagos
    moras.value = porAprobar
  } catch (error) {
    tratar(error)
    return
  }
  // Primero las moras: mientras esperan, la cuota no se paga.
  const lista = [
    ...moras.value.map((m) => ({ tipo: 'mora' as const, id: m.id })),
    ...(pendientes.value ?? []).map((p) => ({ tipo: 'pago' as const, id: p.id })),
  ]
  const pedido = typeof route.query.pago === 'string' ? route.query.pago : idElegido()
  const siguiente = lista.find((item) => item.id === pedido) ?? lista[0]
  if (siguiente) await abrir(siguiente.tipo, siguiente.id)
  else elegido.value = null
}

async function alDecidir(mensaje: string) {
  aviso.value = mensaje
  elegido.value = null
  if (route.query.pago) await router.replace({ query: {} })
  await cargar()
}

// Un pago nuevo de la asistente aparece al momento, sin recargar.
watch(() => notificaciones.avisos, cargar)
onMounted(cargar)
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      Los pagos que esperan tu revisión.
    </h1>
    <p class="mt-2 mb-6 max-w-[62ch] text-[13px] text-secundario sm:mb-8">
      Cada comprobante ya pasó la revisión automática. Míralo, compáralo con la confianza y confirma
      el pago, o devuélvelo con un motivo para que tu asistente suba el correcto.
    </p>

    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>
    <BaseAviso v-if="fallo" tono="error" class="mb-6">{{ fallo }}</BaseAviso>

    <div v-if="pendientes === null && !fallo" class="flex justify-center py-16">
      <span
        aria-label="Cargando los pagos por verificar"
        class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
      />
    </div>

    <div
      v-else-if="pendientes && !pendientes.length && !moras.length"
      class="mx-auto max-w-[520px] animate-aparecer rounded-2xl border border-borde bg-white px-6 py-12 text-center"
    >
      <span
        aria-hidden="true"
        class="mx-auto mb-4 grid size-14 place-items-center rounded-full bg-exito-fondo text-exito"
      >
        <BaseIcono nombre="check" class="size-7" />
      </span>
      <h2 class="text-[20px] font-extrabold">No hay pagos ni moras por revisar.</h2>
      <p class="mt-2 text-[13px] text-secundario">
        Cuando tu asistente registre un pago, te llegará un aviso y aparecerá aquí.
      </p>
    </div>

    <div v-else-if="pendientes" class="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-8">
      <nav aria-label="Pagos y moras por revisar" class="flex flex-col gap-5">
        <div v-if="moras.length">
          <h2 class="mb-2 text-[12px] font-bold text-aviso">
            Moras por aprobar · {{ moras.length }}
          </h2>
          <ul class="flex flex-col gap-2">
            <li v-for="mora in moras" :key="mora.id">
              <button
                type="button"
                class="w-full rounded-[12px] border bg-white p-3.5 text-left transition-[border-color,box-shadow] duration-200 hover:shadow-[0_8px_26px_#30233012]"
                :class="idElegido() === mora.id ? 'border-acento' : 'border-borde'"
                :aria-current="idElegido() === mora.id ? 'true' : undefined"
                @click="abrir('mora', mora.id)"
              >
                <span class="flex items-start justify-between gap-3">
                  <strong class="text-[13px] leading-snug">{{ mora.concepto }}</strong>
                  <span class="shrink-0 text-[13px] font-extrabold text-aviso">
                    + {{ formatearSoles(mora.importe) }}
                  </span>
                </span>
                <small class="mt-1 block text-[11px] text-secundario">
                  Mora · {{ mora.declarada_por }}
                </small>
              </button>
            </li>
          </ul>
        </div>
        <div v-if="pendientes.length">
          <h2 class="mb-2 text-[12px] font-bold text-secundario">
            Por verificar · {{ pendientes.length }}
          </h2>
          <ul class="flex flex-col gap-2">
            <li v-for="pago in pendientes" :key="pago.id">
              <button
                type="button"
                class="w-full rounded-[12px] border bg-white p-3.5 text-left transition-[border-color,box-shadow] duration-200 hover:shadow-[0_8px_26px_#30233012]"
                :class="idElegido() === pago.id ? 'border-acento' : 'border-borde'"
                :aria-current="idElegido() === pago.id ? 'true' : undefined"
                @click="abrir('pago', pago.id)"
              >
                <span class="flex items-start justify-between gap-3">
                  <strong class="text-[13px] leading-snug">{{ pago.concepto }}</strong>
                  <span class="shrink-0 text-[13px] font-extrabold">
                    {{ formatearSoles(pago.importe) }}
                  </span>
                </span>
                <small class="mt-1 block text-[11px] text-secundario">
                  {{ pago.registrado_por }} · {{ formatearFecha(pago.pagado_el) }}
                </small>
                <span
                  v-if="pago.confianza !== null"
                  class="mt-2 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold"
                  :class="
                    pago.confianza >= 80
                      ? 'bg-exito-fondo text-exito'
                      : pago.confianza >= 60
                        ? 'bg-aviso-fondo text-aviso'
                        : 'bg-error-fondo text-error'
                  "
                >
                  Confianza {{ pago.confianza }} %
                </span>
              </button>
            </li>
          </ul>
        </div>
      </nav>

      <div class="min-w-0 rounded-2xl border border-borde bg-white p-5 sm:p-6">
        <DetallePago
          v-if="elegido?.tipo === 'pago'"
          :pago="elegido.pago"
          @decidido="alDecidir"
          @sesion-terminada="sesionTerminada"
        />
        <DetalleMora
          v-else-if="elegido?.tipo === 'mora'"
          :mora="elegido.mora"
          @decidido="alDecidir"
          @sesion-terminada="sesionTerminada"
        />
        <div v-else class="flex justify-center py-16">
          <span
            aria-label="Cargando el pago"
            class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
          />
        </div>
      </div>
    </div>
  </section>
</template>
