<script setup lang="ts">
import { computed, ref, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    etiqueta: string
    tipo?: 'text' | 'password' | 'email' | 'tel'
    autocompletar?: string
    error?: string
    /** Indicación mientras se escribe (qué falta); no marca el campo como inválido. */
    aviso?: string
    ayuda?: string
    deshabilitado?: boolean
    soloLectura?: boolean
    /** Nombres propios: el teclado del móvil empieza cada palabra en mayúscula. */
    capitalizar?: boolean
    maximo?: number
    /** Teclado del móvil: numérico para documentos y celulares. */
    modoEntrada?: 'text' | 'numeric' | 'tel' | 'email'
    /** Texto fijo antes del valor, como el código del país (+51). */
    prefijo?: string
    /** Limpia lo escrito o pegado: lo que nunca sería válido no llega a escribirse. */
    filtro?: (valor: string) => string
  }>(),
  {
    tipo: 'text',
    autocompletar: undefined,
    error: undefined,
    aviso: undefined,
    ayuda: undefined,
    deshabilitado: false,
    soloLectura: false,
    capitalizar: false,
    maximo: undefined,
    modoEntrada: undefined,
    prefijo: undefined,
    filtro: undefined,
  },
)

const valor = defineModel<string>({ required: true })
const id = useId()
const entrada = ref<HTMLInputElement>()
const visible = ref(false)

const tipoActual = computed(() =>
  props.tipo === 'password' ? (visible.value ? 'text' : 'password') : props.tipo,
)
const descripcion = computed(
  () =>
    [
      props.error && `${id}-error`,
      !props.error && props.aviso && `${id}-aviso`,
      props.ayuda && `${id}-ayuda`,
    ]
      .filter(Boolean)
      .join(' ') || undefined,
)

function alEscribir(evento: Event) {
  const elemento = evento.target as HTMLInputElement
  const limpio = props.filtro ? props.filtro(elemento.value) : elemento.value
  // Lo rechazado desaparece al instante, sin mover el cursor al final si no hizo falta.
  if (limpio !== elemento.value) elemento.value = limpio
  valor.value = limpio
}

defineExpose({ enfocar: () => entrada.value?.focus() })
</script>

<template>
  <div class="mb-4 flex flex-col gap-1.5">
    <label :for="id" class="text-[12px] font-bold">{{ etiqueta }}</label>
    <div class="relative flex">
      <span
        v-if="prefijo"
        aria-hidden="true"
        class="inline-flex shrink-0 items-center rounded-l-[7px] border border-r-0 border-control bg-fondo px-3 text-[14px] text-secundario"
      >
        {{ prefijo }}
      </span>
      <input
        :id="id"
        ref="entrada"
        :value="valor"
        :type="tipoActual"
        :autocomplete="autocompletar"
        :inputmode="modoEntrada"
        :disabled="deshabilitado"
        :readonly="soloLectura"
        :maxlength="maximo"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="descripcion"
        spellcheck="false"
        :autocapitalize="capitalizar ? 'words' : 'none'"
        class="min-h-[46px] w-full min-w-0 border bg-white px-3 py-2.5 text-[14px] text-tinta transition-colors duration-200 placeholder:text-secundario read-only:border-borde read-only:bg-fondo read-only:text-secundario disabled:bg-fondo"
        :class="[
          error ? 'border-error' : 'border-control enabled:read-write:hover:border-tinta',
          tipo === 'password' ? 'pr-20' : '',
          prefijo ? 'rounded-r-[7px]' : 'rounded-[7px]',
        ]"
        @input="alEscribir"
      />
      <button
        v-if="tipo === 'password'"
        type="button"
        class="absolute inset-y-1 right-1 rounded-md px-2.5 text-[12px] font-bold text-acento hover:bg-acento-suave"
        :aria-pressed="visible"
        :aria-label="
          visible ? `Ocultar ${etiqueta.toLowerCase()}` : `Mostrar ${etiqueta.toLowerCase()}`
        "
        @click="visible = !visible"
      >
        {{ visible ? 'Ocultar' : 'Mostrar' }}
      </button>
    </div>
    <p v-if="error" :id="`${id}-error`" class="animate-aparecer text-[12px] text-error">
      {{ error }}
    </p>
    <p
      v-else-if="aviso"
      :id="`${id}-aviso`"
      class="animate-aparecer text-[12px] text-aviso"
      aria-live="polite"
    >
      {{ aviso }}
    </p>
    <p v-if="ayuda" :id="`${id}-ayuda`" class="text-[12px] text-secundario">{{ ayuda }}</p>
    <slot />
  </div>
</template>
