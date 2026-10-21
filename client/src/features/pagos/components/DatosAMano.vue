<script setup lang="ts">
import { reactive, ref, useId } from 'vue'

import { LUGARES_PAGO } from '@/features/deudas/catalogo'
import { filtrarImporte } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseBoton from '@/shared/components/BaseBoton.vue'

import { completarComprobante } from '../api/pagos'
import type { Comprobante, DatosAMano } from '../types'

/**
 * Los datos de un voucher que no se pudo leer solo. El backend los pasa por las mismas reglas que
 * lo leído y el pago llega al gerente con poca confianza, para que mire el voucher.
 */
const props = defineProps<{ comprobanteId: string; importe: string; hoy: string }>()
const emit = defineEmits<{ completado: [comprobante: Comprobante] }>()

const datos = reactive<DatosAMano>({
  importe: props.importe,
  pagado_el: props.hoy,
  numero_operacion: '',
  lugar: null,
  comision: '',
})
const errores = ref<Record<string, string>>({})
const fallo = ref<string | null>(null)
const enviando = ref(false)
const ids = {
  importe: useId(),
  fecha: useId(),
  operacion: useId(),
  lugar: useId(),
  comision: useId(),
}

async function enviar() {
  enviando.value = true
  errores.value = {}
  fallo.value = null
  try {
    emit('completado', await completarComprobante(props.comprobanteId, datos))
  } catch (error) {
    if (error instanceof ErrorApi && Object.keys(error.campos).length) errores.value = error.campos
    else fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
  } finally {
    enviando.value = false
  }
}

const campo = (clave: string) =>
  `mt-1 min-h-10 w-full rounded-[7px] border bg-white px-3 text-[13px] ${
    errores.value[clave] ? 'border-error' : 'border-control hover:border-tinta'
  }`
</script>

<template>
  <form
    class="mt-3 grid grid-cols-1 gap-3 rounded-[10px] bg-fondo p-3 sm:grid-cols-2"
    novalidate
    aria-label="Escribe los datos del voucher"
    @submit.prevent="enviar"
  >
    <p class="text-[12px] text-secundario sm:col-span-2">
      Escríbelos tal como aparecen en el voucher. Tu gerente lo revisará antes de confirmar el pago.
    </p>
    <div>
      <label :for="ids.importe" class="text-[12px] font-bold">Importe pagado (S/)</label>
      <input
        :id="ids.importe"
        :value="datos.importe"
        inputmode="decimal"
        :aria-invalid="errores.importe ? 'true' : undefined"
        :class="campo('importe')"
        @input="datos.importe = filtrarImporte(($event.target as HTMLInputElement).value)"
      />
      <p v-if="errores.importe" class="mt-1 text-[11px] text-error">{{ errores.importe }}</p>
    </div>
    <div>
      <label :for="ids.fecha" class="text-[12px] font-bold">Fecha del pago</label>
      <input
        :id="ids.fecha"
        v-model="datos.pagado_el"
        type="date"
        :max="hoy"
        :aria-invalid="errores.pagado_el ? 'true' : undefined"
        :class="campo('pagado_el')"
      />
      <p v-if="errores.pagado_el" class="mt-1 text-[11px] text-error">{{ errores.pagado_el }}</p>
    </div>
    <div>
      <label :for="ids.operacion" class="text-[12px] font-bold">Número de operación</label>
      <input
        :id="ids.operacion"
        v-model="datos.numero_operacion"
        maxlength="40"
        autocomplete="off"
        :aria-invalid="errores.numero_operacion ? 'true' : undefined"
        :class="campo('numero_operacion')"
      />
      <p v-if="errores.numero_operacion" class="mt-1 text-[11px] text-error">
        {{ errores.numero_operacion }}
      </p>
    </div>
    <div>
      <label :for="ids.lugar" class="text-[12px] font-bold">Dónde pagaste</label>
      <select
        :id="ids.lugar"
        v-model="datos.lugar"
        :aria-invalid="errores.lugar ? 'true' : undefined"
        :class="campo('lugar')"
      >
        <option :value="null" disabled>Elige el lugar</option>
        <option v-for="l in LUGARES_PAGO" :key="l.valor" :value="l.valor">{{ l.etiqueta }}</option>
      </select>
      <p v-if="errores.lugar" class="mt-1 text-[11px] text-error">{{ errores.lugar }}</p>
    </div>
    <div>
      <label :for="ids.comision" class="text-[12px] font-bold">Comisión aparte (opcional)</label>
      <input
        :id="ids.comision"
        :value="datos.comision"
        inputmode="decimal"
        :aria-invalid="errores.comision ? 'true' : undefined"
        :class="campo('comision')"
        @input="datos.comision = filtrarImporte(($event.target as HTMLInputElement).value)"
      />
      <p v-if="errores.comision" class="mt-1 text-[11px] text-error">{{ errores.comision }}</p>
    </div>
    <div class="flex items-end justify-end">
      <BaseBoton tipo="submit" :cargando="enviando">Usar estos datos</BaseBoton>
    </div>
    <p v-if="fallo" role="alert" class="text-[12px] text-error sm:col-span-2">{{ fallo }}</p>
  </form>
</template>
