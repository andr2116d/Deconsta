<script setup lang="ts">
import { computed, useId, watch } from 'vue'

import BaseCampo from '@/shared/components/BaseCampo.vue'
import { avisoDocumento, filtrarCarne, filtrarDni } from '@/shared/validaciones/persona'

import type { TipoDocumentoTitular } from '../types'

/**
 * Documento opcional del titular: DNI, carné de extranjería o RUC (por ejemplo, de su empresa).
 * El número solo admite lo que su tipo permite y avisa lo que falta; el backend valida el resto,
 * incluido el dígito verificador del RUC.
 */
withDefaults(defineProps<{ error?: string; errorTipo?: string }>(), {
  error: undefined,
  errorTipo: undefined,
})

const tipo = defineModel<TipoDocumentoTitular | null>('tipo', { required: true })
const numero = defineModel<string>('numero', { required: true })

const LONGITUD_RUC = 11
const filtrarRuc = (valor: string) => valor.replace(/\D/g, '').slice(0, LONGITUD_RUC)
const FILTROS = { dni: filtrarDni, ce: filtrarCarne, ruc: filtrarRuc }
const ETIQUETAS = { dni: 'Número de DNI', ce: 'Número de carné', ruc: 'Número de RUC' }

const idTipo = useId()
const filtro = computed(() => (tipo.value ? FILTROS[tipo.value] : undefined))
const aviso = computed(() => {
  if (!tipo.value || !numero.value) return undefined
  if (tipo.value !== 'ruc') return avisoDocumento(tipo.value, numero.value)
  const faltan = LONGITUD_RUC - numero.value.length
  return faltan > 0 ? `El RUC tiene 11 dígitos. Faltan ${faltan}.` : undefined
})

// Al cambiar de tipo, el número conserva solo lo que el nuevo tipo admite.
watch(tipo, (nuevo) => (numero.value = nuevo ? FILTROS[nuevo](numero.value) : ''))
</script>

<template>
  <fieldset>
    <legend class="sr-only">Documento del titular</legend>
    <div class="grid gap-x-4 sm:grid-cols-[minmax(0,190px)_1fr]">
      <div class="mb-4 flex flex-col gap-1.5">
        <label :for="idTipo" class="text-[12px] font-bold">
          Documento <span class="font-normal text-secundario">(opcional)</span>
        </label>
        <select
          :id="idTipo"
          v-model="tipo"
          :aria-invalid="errorTipo ? 'true' : undefined"
          class="min-h-[46px] w-full rounded-[7px] border bg-white px-3 text-[14px] text-tinta transition-colors duration-200 hover:border-tinta"
          :class="errorTipo ? 'border-error' : 'border-control'"
        >
          <option :value="null">Sin documento</option>
          <option value="dni">DNI</option>
          <option value="ce">Carné de extranjería</option>
          <option value="ruc">RUC</option>
        </select>
        <p v-if="errorTipo" class="text-[12px] text-error">{{ errorTipo }}</p>
      </div>
      <BaseCampo
        v-if="tipo"
        v-model="numero"
        :etiqueta="ETIQUETAS[tipo]"
        autocompletar="off"
        :modo-entrada="tipo === 'ce' ? 'text' : 'numeric'"
        :filtro="filtro"
        :aviso="aviso"
        :error="error"
      />
      <p v-else class="mb-4 self-end pb-3 text-[12px] text-secundario">
        Algunos recibos solo muestran el nombre; otros, el DNI o el RUC del titular.
      </p>
    </div>
  </fieldset>
</template>
