<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import { formatearFecha } from '@/features/deudas/catalogo'
import { useEquipoStore } from '@/features/equipo/stores/equipo'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { pedirPago, retirarPedido } from '../api/pagos'
import type { PedidoResumen } from '../types'

/**
 * El gerente pide a una asistente que pague una cuota («anda págala») o retira el pedido. La
 * asistente verá un aviso a pantalla completa hasta que registre el pago.
 */
const props = defineProps<{
  deudaId: string
  cuota: number
  concepto: string
  importe: string
  venceEl: string
  pedido: PedidoResumen | null
}>()
const emit = defineEmits<{ cambio: [] }>()

const LARGO_NOTA = 500

const equipo = useEquipoStore()
const abierto = ref(false)
const enviando = ref(false)
const asistenteId = ref('')
const nota = ref('')
const error = ref<string | null>(null)
const errores = ref<Record<string, string>>({})
const idAsistente = useId()
const idNota = useId()

// Una asistente bloqueada no puede entrar a ver el pedido.
const disponibles = computed(() => (equipo.asistentes ?? []).filter((a) => !a.bloqueada))
const nombre = (a: { nombres: string; apellidos: string }) => `${a.nombres} ${a.apellidos}`

async function abrir() {
  error.value = null
  errores.value = {}
  nota.value = ''
  abierto.value = true
  if (!equipo.asistentes) {
    try {
      await equipo.cargar()
    } catch {
      error.value = 'No pudimos cargar tu equipo. Vuelve a intentarlo.'
    }
  }
  // Con una sola asistente, el pedido va directo a ella.
  asistenteId.value = disponibles.value.length === 1 ? disponibles.value[0]!.id : ''
}

function fallo(e: unknown) {
  error.value = e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado.'
  errores.value = e instanceof ErrorApi ? e.campos : {}
}

async function pedir() {
  if (!asistenteId.value) {
    errores.value = { asistente_id: 'Elige a quién se lo pides.' }
    return
  }
  enviando.value = true
  error.value = null
  errores.value = {}
  try {
    await pedirPago({
      deuda_id: props.deudaId,
      cuota: props.cuota,
      asistente_id: asistenteId.value,
      nota: nota.value.trim() || null,
    })
    abierto.value = false
    emit('cambio')
  } catch (e) {
    fallo(e)
  } finally {
    enviando.value = false
  }
}

async function retirar() {
  if (!props.pedido) return
  enviando.value = true
  error.value = null
  try {
    await retirarPedido(props.pedido.id)
    emit('cambio')
  } catch (e) {
    fallo(e)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="flex flex-col items-start gap-1 sm:items-end">
    <div v-if="pedido" class="flex flex-wrap items-center gap-2">
      <span
        class="inline-flex items-center gap-1 rounded-md bg-aviso-fondo px-2 py-0.5 text-[11px] font-bold text-aviso"
        :title="pedido.nota ?? undefined"
      >
        <BaseIcono nombre="reloj" class="size-3.5" />
        Pedido a {{ pedido.asistente }}
      </span>
      <button
        type="button"
        class="text-[12px] font-bold text-acento hover:underline disabled:opacity-60"
        :disabled="enviando"
        :aria-label="`Retirar el pedido de pagar ${concepto}`"
        @click="retirar"
      >
        Retirar
      </button>
    </div>
    <button
      v-else
      type="button"
      class="inline-flex items-center gap-1 text-[12px] font-bold text-acento hover:underline"
      :aria-label="`Pedir que paguen ${concepto}`"
      @click="abrir"
    >
      <BaseIcono nombre="reloj" class="size-3.5" />
      Pedir que la paguen
    </button>
    <p v-if="error && !abierto" role="alert" class="text-[11px] text-error">{{ error }}</p>

    <BaseDialogo :abierto="abierto" titulo="Pide completar este pago." @cerrar="abierto = false">
      <template #icono>
        <BaseIcono nombre="reloj" class="size-5" />
      </template>
      <p class="mt-3 text-[13px] text-secundario">
        Le saldrá un aviso al entrar, y volverá mientras la cuota siga sin pagar.
      </p>
      <div class="mt-4 flex items-center justify-between gap-3 rounded-[10px] bg-fondo px-3.5 py-3">
        <span class="min-w-0">
          <strong class="block truncate text-[13px]">{{ concepto }}</strong>
          <small class="text-[11px] text-secundario">Vence el {{ formatearFecha(venceEl) }}</small>
        </span>
        <strong class="shrink-0 text-[15px]">{{ formatearSoles(importe) }}</strong>
      </div>

      <p v-if="equipo.asistentes && !disponibles.length" class="mt-4 text-[13px] text-error">
        No tienes asistentes que puedan entrar. Registra o desbloquea una en Mi equipo.
      </p>
      <form v-else class="mt-4 flex flex-col gap-4" novalidate @submit.prevent="pedir">
        <div>
          <label :for="idAsistente" class="text-[12px] font-bold">Asistente</label>
          <select
            :id="idAsistente"
            v-model="asistenteId"
            :aria-invalid="errores.asistente_id ? 'true' : undefined"
            class="mt-1.5 min-h-11 w-full rounded-[7px] border bg-white px-3 text-[14px]"
            :class="errores.asistente_id ? 'border-error' : 'border-control hover:border-tinta'"
          >
            <option value="" disabled>Elige a quién</option>
            <option v-for="a in disponibles" :key="a.id" :value="a.id">{{ nombre(a) }}</option>
          </select>
          <p v-if="errores.asistente_id" class="mt-1 text-[12px] text-error">
            {{ errores.asistente_id }}
          </p>
        </div>
        <div>
          <label :for="idNota" class="text-[12px] font-bold">Nota (opcional)</label>
          <textarea
            :id="idNota"
            v-model="nota"
            rows="2"
            :maxlength="LARGO_NOTA"
            placeholder="Por ejemplo: págalo antes de las 4 p. m. para evitar el corte."
            :aria-invalid="errores.nota ? 'true' : undefined"
            class="mt-1.5 w-full rounded-[7px] border bg-white px-3 py-2.5 text-[14px]"
            :class="errores.nota ? 'border-error' : 'border-control hover:border-tinta'"
          />
          <p v-if="errores.nota" class="mt-1 text-[12px] text-error">{{ errores.nota }}</p>
        </div>
        <p v-if="error" role="alert" class="text-[12px] text-error">{{ error }}</p>
        <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <BaseBoton variante="discreto" @click="abierto = false">Volver</BaseBoton>
          <BaseBoton tipo="submit" :cargando="enviando">Enviar el pedido</BaseBoton>
        </div>
      </form>
    </BaseDialogo>
  </div>
</template>
