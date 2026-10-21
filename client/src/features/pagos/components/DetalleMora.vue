<script setup lang="ts">
import { ref } from 'vue'

import DialogoMotivo from '@/features/deudas/components/DialogoMotivo.vue'
import VistaDocumento from '@/features/deudas/components/VistaDocumento.vue'
import { formatearFecha } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import { aprobarMora, descargarComprobante, rechazarMora } from '../api/pagos'
import type { MoraDetalle, ResultadoComprobacion } from '../types'
import MedidorConfianza from './MedidorConfianza.vue'

/**
 * La mora que declaró la asistente, con su prueba y lo comprobado. Mientras el gerente no decide,
 * la cuota no se paga; aprobada, el pago puede incluirla.
 */
const props = defineProps<{ mora: MoraDetalle }>()
const emit = defineEmits<{ decidido: [mensaje: string]; 'sesion-terminada': [] }>()

const ocupado = ref(false)
const rechazando = ref(false)
const fallo = ref<string | null>(null)
const errorMotivo = ref<string | undefined>()

const RESULTADOS: Record<ResultadoComprobacion, { icono: NombreIcono; clase: string }> = {
  bien: { icono: 'check', clase: 'bg-exito-fondo text-exito' },
  sin_dato: { icono: 'reloj', clase: 'bg-fondo text-secundario' },
  aviso: { icono: 'alerta', clase: 'bg-aviso-fondo text-aviso' },
}

async function decidir(accion: () => Promise<unknown>, mensaje: string) {
  ocupado.value = true
  fallo.value = null
  try {
    await accion()
    rechazando.value = false
    emit('decidido', mensaje)
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    if (rechazando.value && error instanceof ErrorApi && error.campos.motivo) {
      errorMotivo.value = error.campos.motivo
    } else {
      rechazando.value = false
      fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
    }
  } finally {
    ocupado.value = false
  }
}

const aprobar = () =>
  decidir(
    () => aprobarMora(props.mora.id),
    `Aprobaste la mora de «${props.mora.concepto}». ${props.mora.declarada_por} ya puede pagar.`,
  )

function rechazar(motivo: string) {
  errorMotivo.value = undefined
  return decidir(
    () => rechazarMora(props.mora.id, motivo),
    `Rechazaste la mora de «${props.mora.concepto}». La cuota se pagará sin ella.`,
  )
}
</script>

<template>
  <article class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div class="min-w-0">
      <VistaDocumento
        v-if="mora.prueba"
        :documento-id="mora.prueba.id"
        :tipo="mora.prueba.tipo_archivo"
        :titulo="`Prueba de la mora de ${mora.concepto}`"
        :descargar="descargarComprobante"
      />
      <ul v-if="mora.prueba?.senales.length" class="mt-3 flex flex-col gap-1.5">
        <li
          v-for="senal in mora.prueba.senales"
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
      <span
        class="inline-flex rounded-md bg-aviso-fondo px-2 py-0.5 text-[11px] font-bold text-aviso"
      >
        Mora por aprobar
      </span>
      <h2 class="mt-3 text-[22px] leading-tight font-extrabold tracking-[-0.02em]">
        {{ mora.concepto }}
      </h2>
      <p class="mt-1 text-[12px] text-secundario">
        Declaró {{ mora.declarada_por }} el {{ formatearFecha(mora.declarada_en.slice(0, 10)) }}
      </p>
      <dl class="mt-4 grid grid-cols-3 gap-3 text-[12px]">
        <div>
          <dt class="text-[11px] text-secundario">Cuota</dt>
          <dd class="text-[15px] font-bold">{{ formatearSoles(mora.importe_cuota) }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Mora</dt>
          <dd class="text-[15px] font-bold text-aviso">+ {{ formatearSoles(mora.importe) }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Total</dt>
          <dd class="text-[15px] font-extrabold">
            {{ formatearSoles(Number(mora.importe_cuota) + Number(mora.importe)) }}
          </dd>
        </div>
      </dl>
      <blockquote v-if="mora.nota" class="mt-4 rounded-[10px] bg-fondo p-3 text-[12px]">
        «{{ mora.nota }}»
      </blockquote>

      <MedidorConfianza v-if="mora.confianza !== null" class="mt-5" :confianza="mora.confianza" />
      <ul v-if="mora.comprobaciones" class="mt-5 flex flex-col gap-2">
        <li
          v-for="c in mora.comprobaciones"
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
        <BaseBoton variante="secundario" :deshabilitado="ocupado" @click="rechazando = true">
          Rechazar
        </BaseBoton>
        <BaseBoton :cargando="ocupado && !rechazando" @click="aprobar">
          Aprobar la mora
          <BaseIcono nombre="check" class="size-4" />
        </BaseBoton>
      </div>
    </div>

    <DialogoMotivo
      :abierto="rechazando"
      accion="rechazar-mora"
      :concepto="mora.concepto"
      :enviando="ocupado"
      :error="errorMotivo"
      @confirmar="rechazar"
      @cerrar="rechazando = false"
    />
  </article>
</template>
