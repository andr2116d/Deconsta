<script setup lang="ts">
import { computed, nextTick, useId, watch } from 'vue'

import { avisoDocumento, filtrarDocumento, type TipoDocumento } from '@/shared/validaciones/persona'

import BaseCampo from './BaseCampo.vue'

/**
 * Tipo y número de documento. El número solo admite lo que su tipo permite (8 dígitos para el
 * DNI; letras y dígitos, hasta 12, para el carné) y avisa lo que falta mientras se escribe.
 *
 * Quien lo usa puede no aceptar un cambio de tipo (por ejemplo, para advertir antes): si no
 * actualiza `tipo`, el selector vuelve a su valor.
 */
const props = withDefaults(
  defineProps<{
    error?: string
    ayuda?: string
    tipoBloqueado?: boolean
  }>(),
  { error: undefined, ayuda: undefined, tipoBloqueado: false },
)

const tipo = defineModel<TipoDocumento>('tipo', { required: true })
const numero = defineModel<string>('numero', { required: true })

const idTipo = useId()
const etiqueta = computed(() =>
  tipo.value === 'dni' ? 'Número de DNI' : 'Número de carné de extranjería',
)
const aviso = computed(() => (props.error ? undefined : avisoDocumento(tipo.value, numero.value)))

// Al cambiar de tipo, el número conserva solo lo que el nuevo tipo admite.
watch(tipo, (nuevo) => {
  numero.value = filtrarDocumento(nuevo)(numero.value)
})

async function elegirTipo(evento: Event) {
  const selector = evento.target as HTMLSelectElement
  tipo.value = selector.value as TipoDocumento
  await nextTick()
  selector.value = tipo.value
}
</script>

<template>
  <fieldset>
    <legend class="sr-only">Documento de identidad</legend>
    <div class="grid gap-x-5 sm:grid-cols-[minmax(0,220px)_1fr]">
      <div class="mb-4 flex flex-col gap-1.5">
        <label :for="idTipo" class="text-[12px] font-bold">Tipo de documento</label>
        <select
          :id="idTipo"
          :value="tipo"
          :disabled="tipoBloqueado"
          class="min-h-[46px] w-full rounded-[7px] border border-control bg-white px-3 text-[14px] text-tinta transition-colors duration-200 enabled:hover:border-tinta disabled:border-borde disabled:bg-fondo disabled:text-secundario"
          @change="elegirTipo"
        >
          <option value="dni">DNI</option>
          <option value="ce">Carné de extranjería</option>
        </select>
      </div>
      <div data-campo="numero_documento">
        <BaseCampo
          v-model="numero"
          :etiqueta="etiqueta"
          :modo-entrada="tipo === 'dni' ? 'numeric' : 'text'"
          :filtro="filtrarDocumento(tipo)"
          :error="error"
          :aviso="aviso"
          :ayuda="ayuda"
          autocompletar="off"
        />
      </div>
    </div>
    <slot />
  </fieldset>
</template>
