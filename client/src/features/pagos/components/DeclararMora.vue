<script setup lang="ts">
import { computed, onMounted, ref, useId } from 'vue'

import { ACEPTAR } from '@/features/deudas/composables/useAnalisisDocumento'
import {
  avisoImporte,
  filtrarImporte,
  formatearSoles,
  normalizarImporte,
} from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'

import { declararMora } from '../api/pagos'
import { useComprobantes } from '../composables/useComprobantes'
import type { CuotaPorPagar, Mora } from '../types'
import ComprobanteCargado from './ComprobanteCargado.vue'

/**
 * La mora de una cuota vencida, con su prueba: el documento de la empresa con el monto con mora o
 * el voucher que ya la pagó. Se analiza como un comprobante y el gerente decide; el backend
 * compara la mora declarada con la de la prueba.
 */
const props = defineProps<{
  cuota: CuotaPorPagar
  /** El voucher que pagó con mora: sirve de prueba sin volver a elegirlo. */
  archivoInicial?: File | null
  moraInicial?: string | null
}>()
const emit = defineEmits<{ declarada: [mora: Mora]; cancelar: []; 'sesion-terminada': [] }>()

const importe = ref(props.moraInicial ?? '')
const nota = ref('')
const errores = ref<Record<string, string>>({})
const fallo = ref<string | null>(null)
const enviando = ref(false)
const entrada = ref<HTMLInputElement>()
const idAyuda = useId()

const { vouchers, listos, trabajando, agregar, quitar } = useComprobantes(
  () => props.cuota.deuda_id,
  () => props.cuota.cuota,
  'mora',
)
const prueba = computed(() => vouchers[0] ?? null)
const total = computed(() => {
  const mora = Number(normalizarImporte(importe.value))
  return Number.isFinite(mora) && mora > 0 ? Number(props.cuota.importe) + mora : null
})

function elegir(evento: Event) {
  const elemento = evento.target as HTMLInputElement
  const archivo = elemento.files?.[0]
  elemento.value = ''
  if (!archivo) return
  if (prueba.value) quitar(prueba.value.clave)
  void agregar(archivo)
}

async function enviar() {
  const lista = listos.value[0]?.comprobante
  if (!lista || enviando.value) return
  enviando.value = true
  errores.value = {}
  fallo.value = null
  try {
    const mora = await declararMora({
      deuda_id: props.cuota.deuda_id,
      cuota: props.cuota.cuota,
      importe: normalizarImporte(importe.value),
      prueba_id: lista.id,
      nota: nota.value.trim() || null,
    })
    emit('declarada', mora)
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    if (error instanceof ErrorApi && Object.keys(error.campos).length) errores.value = error.campos
    else fallo.value = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
  } finally {
    enviando.value = false
  }
}

onMounted(() => {
  if (props.archivoInicial) void agregar(props.archivoInicial)
})
</script>

<template>
  <form
    class="animate-aparecer rounded-[14px] border border-acento/40 bg-white p-5"
    novalidate
    aria-labelledby="titulo-mora"
    @submit.prevent="enviar"
  >
    <h2 id="titulo-mora" class="text-[15px] font-extrabold">Declara la mora</h2>
    <p class="mt-1 mb-4 text-[12px] text-secundario">
      Sube la prueba: el documento de la empresa con el monto con mora, o el voucher que ya la pagó.
      Tu gerente la revisará y, mientras decide, la cuota no se paga.
    </p>

    <BaseCampo
      :model-value="importe"
      etiqueta="Mora que cobra la empresa (S/)"
      modo-entrada="decimal"
      :filtro="filtrarImporte"
      :error="errores.importe"
      :aviso="avisoImporte(importe)"
      :ayuda="
        total
          ? `Con la cuota de ${formatearSoles(cuota.importe)}, el total sería ${formatearSoles(total)}.`
          : 'Solo el recargo por el atraso, sin la cuota.'
      "
      @update:model-value="importe = $event"
    />

    <input
      ref="entrada"
      type="file"
      class="sr-only"
      tabindex="-1"
      aria-hidden="true"
      :accept="ACEPTAR"
      @change="elegir"
    />
    <ComprobanteCargado
      v-if="prueba"
      :voucher="prueba"
      :numero="1"
      :bloqueado="enviando"
      @quitar="quitar(prueba.clave)"
    />
    <div v-else class="flex flex-col items-start gap-2">
      <p :id="idAyuda" class="text-[12px] text-secundario">
        Una foto o captura de hasta 10 MB donde se vean el código y el total con la mora.
      </p>
      <BaseBoton variante="secundario" :aria-describedby="idAyuda" @click="entrada?.click()">
        Elegir la prueba
      </BaseBoton>
    </div>
    <p v-if="errores.prueba_id" class="mt-1.5 text-[12px] text-error">{{ errores.prueba_id }}</p>

    <label for="nota-mora" class="mt-4 block text-[12px] font-bold">Nota para tu gerente</label>
    <textarea
      id="nota-mora"
      v-model="nota"
      rows="2"
      maxlength="500"
      placeholder="Opcional. Por ejemplo: el agente me cobró el recargo al pagar."
      class="mt-1.5 w-full rounded-[7px] border border-control bg-white px-3 py-2.5 text-[14px] hover:border-tinta"
    />

    <BaseAviso v-if="fallo" tono="error" class="mt-3">{{ fallo }}</BaseAviso>
    <div class="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <BaseBoton variante="discreto" @click="emit('cancelar')">Ahora no</BaseBoton>
      <BaseBoton
        tipo="submit"
        :cargando="enviando"
        :deshabilitado="!listos.length || trabajando || !importe"
      >
        Enviar al gerente
      </BaseBoton>
    </div>
  </form>
</template>
