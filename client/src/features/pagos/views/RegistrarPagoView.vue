<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useId } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { cuandoVence } from '@/features/calendario/fechas'
import { ACEPTAR } from '@/features/deudas/composables/useAnalisisDocumento'
import { formatearFecha, nombresLugares, textoVencida } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { listarPorPagar, registrarPago } from '../api/pagos'
import ComprobanteCargado from '../components/ComprobanteCargado.vue'
import ConfirmacionPago from '../components/ConfirmacionPago.vue'
import { aCentimos, MAXIMO_VOUCHERS, useComprobantes } from '../composables/useComprobantes'
import type { CuotaPorPagar, Pago } from '../types'

/**
 * Registrar el pago de una cuota: se suben los vouchers (varios si un agente la cobró por partes),
 * cada uno se revisa contra la cuota y, cuando los listos suman la cuota, se registra. El backend
 * vuelve a comprobarlo todo; aquí solo se orienta.
 */
const route = useRoute()
const router = useRouter()
const sesion = useSesionStore()
const rol = computed(() => sesion.usuario?.rol ?? 'asistente')

const carga = ref<'cargando' | 'listo' | 'no_disponible' | 'error'>('cargando')
const cuota = ref<CuotaPorPagar | null>(null)
const hoy = ref('')
const pausado = ref(false)
const pago = ref<Pago | null>(null)
const enviando = ref(false)
const fallo = ref<ErrorApi | null>(null)
const entrada = ref<HTMLInputElement>()
const encima = ref(false)
const idAyuda = useId()

const {
  vouchers,
  listos,
  trabajando,
  sumaCentimos,
  bloqueado: bloqueadoAhora,
  agregar,
  quitar,
} = useComprobantes(
  () => cuota.value?.deuda_id ?? '',
  () => cuota.value?.cuota ?? 1,
)

const bloqueado = computed(() => pausado.value || bloqueadoAhora.value)
const cuotaCentimos = computed(() => aCentimos(cuota.value?.importe))
const faltaCentimos = computed(() => cuotaCentimos.value - sumaCentimos.value)
const soles = (centimos: number) => formatearSoles(centimos / 100)
const porPartes = computed(
  () =>
    faltaCentimos.value > 0 &&
    listos.value.some((v) => v.comprobante?.senales.some((s) => s.codigo === 'PAGO_PARCIAL')),
)
const puedeRegistrar = computed(
  () =>
    listos.value.length > 0 && !trabajando.value && faltaCentimos.value === 0 && !bloqueado.value,
)
const lleno = computed(() => vouchers.length >= MAXIMO_VOUCHERS)

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

async function cargar() {
  carga.value = 'cargando'
  const deudaId = String(route.query.deuda ?? '')
  // Sin cuota (desde un aviso), la próxima que falta pagar de esa deuda.
  const numero = route.query.cuota ? Number(route.query.cuota) : null
  try {
    const porPagar = await listarPorPagar()
    hoy.value = porPagar.hoy
    pausado.value = porPagar.registro_bloqueado
    cuota.value =
      porPagar.cuotas.find(
        (c) => c.deuda_id === deudaId && (numero === null || c.cuota === numero),
      ) ?? null
    carga.value = cuota.value ? 'listo' : 'no_disponible'
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') return sesionTerminada()
    carga.value = 'error'
  }
}

function tomar(lista: FileList | null | undefined) {
  for (const archivo of Array.from(lista ?? [])) {
    if (vouchers.length >= MAXIMO_VOUCHERS) break
    void agregar(archivo)
  }
}

function alElegir(evento: Event) {
  const elemento = evento.target as HTMLInputElement
  tomar(elemento.files)
  elemento.value = ''
}

function alSoltar(evento: DragEvent) {
  encima.value = false
  if (!bloqueado.value) tomar(evento.dataTransfer?.files)
}

async function registrar() {
  if (!cuota.value || !puedeRegistrar.value || enviando.value) return
  enviando.value = true
  fallo.value = null
  try {
    pago.value = await registrarPago({
      deuda_id: cuota.value.deuda_id,
      cuota: cuota.value.cuota,
      comprobantes: listos.value.map((v) => v.comprobante!.id),
    })
    await nextTick()
    document.getElementById('titulo-seccion')?.focus()
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') return sesionTerminada()
    fallo.value =
      error instanceof ErrorApi
        ? error
        : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
    if (fallo.value.codigo === 'REGISTRO_PAGOS_BLOQUEADO') pausado.value = true
  } finally {
    enviando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <ConfirmacionPago v-if="pago" :pago="pago" :rol="rol" />

  <section v-else aria-labelledby="titulo-seccion">
    <RouterLink
      :to="{ name: rol === 'asistente' ? 'pagos-por-completar' : 'calendario' }"
      class="mb-4 inline-flex min-h-8 items-center gap-1 text-[12px] font-bold text-acento hover:underline"
    >
      <BaseIcono nombre="derecha" class="size-3.5 rotate-180" />
      {{ rol === 'asistente' ? 'Pagos por completar' : 'Calendario' }}
    </RouterLink>
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      Deja constancia del pago.
    </h1>
    <p class="mt-2 mb-6 max-w-[62ch] text-[13px] text-secundario">
      Sube el voucher o la captura de la operación. Revisamos que corresponda a esta cuota antes de
      registrarlo.
    </p>

    <div
      v-if="carga === 'cargando'"
      aria-hidden="true"
      class="h-[260px] rounded-[14px] border border-borde bg-white motion-safe:animate-pulse"
    />

    <div v-else-if="carga === 'error'" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" titulo="No pudimos cargar la cuota" class="w-full">
        Revisa tu conexión y vuelve a intentarlo.
      </BaseAviso>
      <BaseBoton variante="secundario" @click="cargar">Volver a intentar</BaseBoton>
    </div>

    <BaseAviso
      v-else-if="carga === 'no_disponible' || !cuota"
      tono="info"
      titulo="Esta cuota ya no está por pagar"
    >
      Puede que ya tenga un pago registrado, que espere la autorización del gerente o que la deuda
      se haya anulado.
    </BaseAviso>

    <div v-else class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-8">
      <div class="flex min-w-0 flex-col gap-4">
        <article class="rounded-[14px] border border-borde bg-white p-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-[18px] font-extrabold">{{ cuota.concepto }}</h2>
              <p class="mt-0.5 text-[12px] text-secundario">
                <template v-if="cuota.cuotas > 1">
                  Cuota {{ cuota.cuota }} de {{ cuota.cuotas }} ·
                </template>
                <template v-if="cuota.codigo_pago">Código {{ cuota.codigo_pago }} · </template>
                Se paga en: {{ nombresLugares(cuota.lugares_pago) }}
              </p>
            </div>
            <strong class="text-[26px] font-extrabold tracking-[-0.03em]">
              {{ formatearSoles(cuota.importe) }}
            </strong>
          </div>
          <p
            class="mt-3 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold"
            :class="cuota.vencida_hace ? 'bg-error-fondo text-error' : 'bg-fondo text-secundario'"
          >
            <BaseIcono :nombre="cuota.vencida_hace ? 'alerta' : 'calendario'" class="size-3.5" />
            {{
              cuota.vencida_hace
                ? textoVencida(cuota.vencida_hace)
                : cuandoVence(cuota.vence_el, hoy)
            }}
            · {{ formatearFecha(cuota.vence_el) }}
          </p>
        </article>

        <BaseAviso
          v-if="cuota.devuelto_por && !bloqueado"
          tono="aviso"
          titulo="Tu gerente devolvió el pago anterior"
        >
          {{ cuota.devuelto_por }} Sube el comprobante correcto: el anterior ya no se puede usar.
        </BaseAviso>
        <BaseAviso v-if="bloqueado" tono="error" titulo="Tu registro de pagos está en pausa">
          Varios comprobantes no correspondían a sus cuotas. Tu gerente ya recibió un aviso y puede
          permitirte registrar pagos otra vez.
        </BaseAviso>
        <BaseAviso
          v-else-if="cuota.vencida_hace"
          tono="aviso"
          titulo="Ya venció: la empresa pudo cobrar mora"
        >
          Si el voucher paga más que la cuota por la mora, por ahora no se registra aquí: avísale a
          tu gerente. Si pagaste solo la cuota, súbelo con normalidad.
        </BaseAviso>

        <div
          class="flex flex-col items-center rounded-[14px] border border-dashed p-6 text-center transition-colors duration-200"
          :class="[
            encima ? 'border-acento bg-acento-suave' : 'border-[#ad96a6] bg-[#f5f0f4]',
            bloqueado || lleno ? 'opacity-60' : '',
          ]"
          @dragenter.prevent="encima = !bloqueado"
          @dragover.prevent="encima = !bloqueado"
          @dragleave.prevent="encima = false"
          @drop.prevent="alSoltar"
        >
          <input
            ref="entrada"
            type="file"
            multiple
            class="sr-only"
            tabindex="-1"
            aria-hidden="true"
            :accept="ACEPTAR"
            @change="alElegir"
          />
          <span
            aria-hidden="true"
            class="mb-3 grid size-12 place-items-center rounded-[14px] bg-white text-acento"
          >
            <BaseIcono nombre="archivo" class="size-6" />
          </span>
          <h2 class="text-[15px] font-extrabold">
            {{ vouchers.length ? 'Sube otro voucher' : 'Suelta aquí el voucher' }}
          </h2>
          <p :id="idAyuda" class="mt-1.5 mb-4 max-w-[360px] text-[12px] text-secundario">
            Foto o captura de hasta 10 MB donde se vean el importe, la fecha y el número de
            operación. Si el agente te cobró por partes, sube todos sus vouchers.
          </p>
          <BaseBoton
            :aria-describedby="idAyuda"
            :deshabilitado="bloqueado || lleno"
            @click="entrada?.click()"
          >
            Elegir {{ vouchers.length ? 'otro voucher' : 'voucher' }}
          </BaseBoton>
        </div>

        <TransitionGroup
          v-if="vouchers.length"
          tag="div"
          class="flex flex-col gap-3"
          leave-active-class="transition duration-200 ease-in"
          leave-to-class="opacity-0 -translate-x-2"
        >
          <ComprobanteCargado
            v-for="(voucher, indice) in vouchers"
            :key="voucher.clave"
            :voucher="voucher"
            :numero="indice + 1"
            :bloqueado="enviando"
            @quitar="quitar(voucher.clave)"
          />
        </TransitionGroup>
      </div>

      <aside class="flex flex-col gap-4 self-start lg:sticky lg:top-[156px]">
        <div class="rounded-[14px] border border-borde bg-white p-5">
          <h2 class="text-[15px] font-extrabold">Resumen del pago</h2>
          <dl class="mt-3 flex flex-col gap-2 text-[13px]">
            <div class="flex justify-between">
              <dt class="text-secundario">Cuota</dt>
              <dd class="font-bold">{{ formatearSoles(cuota.importe) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-secundario">
                {{ listos.length === 1 ? '1 voucher listo' : `${listos.length} vouchers listos` }}
              </dt>
              <dd class="font-bold">{{ soles(sumaCentimos) }}</dd>
            </div>
            <div
              class="flex justify-between border-t border-dashed border-borde pt-2"
              :class="faltaCentimos === 0 && listos.length ? 'text-exito' : ''"
            >
              <dt>{{ faltaCentimos < 0 ? 'Sobra' : 'Falta' }}</dt>
              <dd class="font-extrabold" aria-live="polite">
                {{ soles(Math.abs(faltaCentimos)) }}
              </dd>
            </div>
          </dl>
          <div
            class="mt-3 h-1.5 overflow-hidden rounded-full bg-fondo"
            role="progressbar"
            aria-label="Cuánto de la cuota cubren los vouchers listos"
            :aria-valuenow="Math.min(100, Math.round((sumaCentimos / (cuotaCentimos || 1)) * 100))"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <span
              class="block h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
              :class="faltaCentimos < 0 ? 'bg-error' : 'bg-acento'"
              :style="{ width: `${Math.min(100, (sumaCentimos / (cuotaCentimos || 1)) * 100)}%` }"
            />
          </div>

          <p v-if="porPartes" class="mt-3 rounded-lg bg-rosa p-3 text-[12px] text-ciruela">
            <strong class="block">¿El agente te lo cobró por partes?</strong>
            Sube los otros vouchers del mismo día: juntos deben sumar la cuota. Falta
            {{ soles(faltaCentimos) }}.
          </p>
          <p v-else-if="faltaCentimos < 0" class="mt-3 text-[12px] text-error">
            Los vouchers listos suman más que la cuota: quita el que no corresponde.
          </p>

          <BaseAviso v-if="fallo" tono="error" class="mt-3 text-left">
            {{ fallo.message }}
          </BaseAviso>
          <BaseBoton
            class="mt-4"
            ancho="completo"
            :cargando="enviando"
            :deshabilitado="!puedeRegistrar"
            @click="registrar"
          >
            Registrar pago
            <BaseIcono nombre="derecha" class="size-4" />
          </BaseBoton>
          <p class="mt-2.5 text-[11px] text-secundario">
            {{
              rol === 'gerente'
                ? 'Quedará confirmado a tu nombre.'
                : 'Tu gerente recibirá un aviso para verificar el pago.'
            }}
          </p>
        </div>
      </aside>
    </div>
  </section>
</template>
