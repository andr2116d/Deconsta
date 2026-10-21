<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import DialogoMotivo from '@/features/deudas/components/DialogoMotivo.vue'
import VistaDocumento from '@/features/deudas/components/VistaDocumento.vue'
import { formatearFecha, LUGARES_PAGO } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import { confirmarPago, descargarComprobante, devolverPago } from '../api/pagos'
import type { PagoDetalle, ResultadoComprobacion } from '../types'
import MedidorConfianza from './MedidorConfianza.vue'

/**
 * La mesa de verificación del gerente: los comprobantes tal como se subieron, lo que se comprobó y
 * la decisión. La revisión automática es una ayuda; la decisión es suya.
 */
const props = defineProps<{ pago: PagoDetalle }>()
const emit = defineEmits<{ decidido: [mensaje: string]; 'sesion-terminada': [] }>()

const ocupado = ref(false)
const devolviendo = ref(false)
const fallo = ref<string | null>(null)
const errorMotivo = ref<string | undefined>()
const visible = ref(0)

watch(
  () => props.pago.id,
  () => {
    visible.value = 0
    fallo.value = null
  },
)

const RESULTADOS: Record<ResultadoComprobacion, { icono: NombreIcono; clase: string }> = {
  bien: { icono: 'check', clase: 'bg-exito-fondo text-exito' },
  sin_dato: { icono: 'reloj', clase: 'bg-fondo text-secundario' },
  aviso: { icono: 'alerta', clase: 'bg-aviso-fondo text-aviso' },
}
const comprobante = computed(() => props.pago.detalle_comprobantes[visible.value] ?? null)
const lugar = computed(
  () => LUGARES_PAGO.find((l) => l.valor === props.pago.lugar_pago)?.etiqueta ?? 'Sin dato',
)

async function decidir(accion: () => Promise<unknown>, mensaje: string) {
  ocupado.value = true
  fallo.value = null
  try {
    await accion()
    devolviendo.value = false
    emit('decidido', mensaje)
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    const mensajeError = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
    if (devolviendo.value && error instanceof ErrorApi && error.campos.motivo) {
      errorMotivo.value = error.campos.motivo
    } else {
      devolviendo.value = false
      fallo.value = mensajeError
    }
  } finally {
    ocupado.value = false
  }
}

const confirmar = () =>
  decidir(
    () => confirmarPago(props.pago.id),
    `Confirmaste el pago de «${props.pago.concepto}». Le avisamos a ${props.pago.registrado_por}.`,
  )

function devolver(motivo: string) {
  errorMotivo.value = undefined
  return decidir(
    () => devolverPago(props.pago.id, motivo),
    `Devolviste el pago de «${props.pago.concepto}». La cuota vuelve a estar por pagar.`,
  )
}
</script>

<template>
  <article class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div class="min-w-0">
      <div
        v-if="pago.detalle_comprobantes.length > 1"
        class="mb-3 flex flex-wrap gap-2"
        role="tablist"
        aria-label="Comprobantes del pago"
      >
        <button
          v-for="(c, indice) in pago.detalle_comprobantes"
          :key="c.id"
          type="button"
          role="tab"
          :aria-selected="visible === indice"
          class="min-h-9 rounded-full border px-3 text-[12px] font-bold transition-colors duration-200"
          :class="
            visible === indice
              ? 'border-acento bg-acento-suave text-acento'
              : 'border-borde bg-white hover:border-control'
          "
          @click="visible = indice"
        >
          Voucher {{ indice + 1 }}
          <template v-if="c.lectura?.importe"> · {{ formatearSoles(c.lectura.importe) }}</template>
        </button>
      </div>
      <VistaDocumento
        v-if="comprobante"
        :documento-id="comprobante.id"
        :tipo="comprobante.tipo_archivo"
        :titulo="`Voucher ${visible + 1} de ${pago.concepto}`"
        :descargar="descargarComprobante"
      />
      <dl
        v-if="comprobante?.lectura"
        class="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 rounded-[10px] bg-fondo p-3.5 text-[12px]"
      >
        <div>
          <dt class="text-[11px] text-secundario">Medio</dt>
          <dd class="font-bold">{{ comprobante.lectura.medio ?? 'Sin dato' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Empresa pagada</dt>
          <dd class="font-bold">{{ comprobante.lectura.empresa ?? 'Sin dato' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Operación</dt>
          <dd class="font-bold">{{ comprobante.lectura.numero_operacion ?? 'Sin dato' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Fecha</dt>
          <dd class="font-bold">
            {{
              comprobante.lectura.pagado_el
                ? formatearFecha(comprobante.lectura.pagado_el)
                : 'Sin dato'
            }}
          </dd>
        </div>
      </dl>
      <ul v-if="comprobante?.senales.length" class="mt-3 flex flex-col gap-1.5">
        <li
          v-for="senal in comprobante.senales"
          :key="senal.codigo"
          class="flex gap-2 text-[12px] leading-snug"
          :class="senal.riesgo === 'medio' ? 'text-aviso' : 'text-secundario'"
        >
          <BaseIcono
            :nombre="senal.riesgo === 'medio' ? 'alerta' : 'destello'"
            class="mt-0.5 size-3.5 shrink-0"
          />
          <span>{{ senal.detalle }}</span>
        </li>
      </ul>
    </div>

    <div class="order-first min-w-0 xl:order-none">
      <span class="inline-flex rounded-md bg-rosa px-2 py-0.5 text-[11px] font-bold text-ciruela">
        Solo tú puedes verificarlo
      </span>
      <h2 class="mt-3 text-[22px] leading-tight font-extrabold tracking-[-0.02em]">
        {{ pago.concepto }}
      </h2>
      <p class="mt-1 text-[12px] text-secundario">
        <template v-if="pago.cuotas > 1">Cuota {{ pago.cuota }} de {{ pago.cuotas }} · </template>
        Pagó {{ pago.registrado_por }} el {{ formatearFecha(pago.pagado_el) }} · {{ lugar }}
      </p>
      <p class="mt-4 text-[34px] leading-none font-extrabold tracking-[-0.03em]">
        {{ formatearSoles(pago.importe) }}
      </p>
      <p v-if="Number(pago.comision) > 0" class="mt-1 text-[12px] text-secundario">
        Más {{ formatearSoles(pago.comision) }} de comisión del agente, aparte.
      </p>

      <MedidorConfianza v-if="pago.confianza !== null" class="mt-5" :confianza="pago.confianza" />

      <ul v-if="pago.comprobaciones" class="mt-5 flex flex-col gap-2">
        <li
          v-for="c in pago.comprobaciones"
          :key="c.codigo"
          class="flex items-start gap-2.5 text-[12px] leading-snug"
        >
          <span
            aria-hidden="true"
            class="grid size-6 shrink-0 place-items-center rounded-full"
            :class="RESULTADOS[c.resultado].clase"
          >
            <BaseIcono :nombre="RESULTADOS[c.resultado].icono" class="size-3.5" />
          </span>
          <span>
            <strong class="block text-[12px]">{{ c.titulo }}</strong>
            <span class="text-secundario">{{ c.detalle }}</span>
          </span>
        </li>
      </ul>

      <BaseAviso v-if="fallo" tono="error" class="mt-5">{{ fallo }}</BaseAviso>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" :deshabilitado="ocupado" @click="devolviendo = true">
          Devolver
        </BaseBoton>
        <BaseBoton :cargando="ocupado && !devolviendo" @click="confirmar">
          Confirmar pago
          <BaseIcono nombre="check" class="size-4" />
        </BaseBoton>
      </div>
    </div>

    <DialogoMotivo
      :abierto="devolviendo"
      accion="devolver"
      :concepto="pago.concepto"
      :enviando="ocupado"
      :error="errorMotivo"
      @confirmar="devolver"
      @cerrar="devolviendo = false"
    />
  </article>
</template>
