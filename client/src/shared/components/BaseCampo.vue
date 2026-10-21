<script setup lang="ts">
import { computed, ref, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    etiqueta: string
    tipo?: 'text' | 'password'
    autocompletar?: string
    error?: string
    ayuda?: string
    deshabilitado?: boolean
  }>(),
  {
    tipo: 'text',
    autocompletar: undefined,
    error: undefined,
    ayuda: undefined,
    deshabilitado: false,
  },
)

const valor = defineModel<string>({ required: true })
const id = useId()
const entrada = ref<HTMLInputElement>()
const visible = ref(false)

const tipoActual = computed(() =>
  props.tipo === 'password' && !visible.value ? 'password' : 'text',
)
const descripcion = computed(
  () =>
    [props.error && `${id}-error`, props.ayuda && `${id}-ayuda`].filter(Boolean).join(' ') ||
    undefined,
)

defineExpose({ enfocar: () => entrada.value?.focus() })
</script>

<template>
  <div class="mb-4 flex flex-col gap-1.5">
    <label :for="id" class="text-[12px] font-bold">{{ etiqueta }}</label>
    <div class="relative">
      <input
        :id="id"
        ref="entrada"
        v-model="valor"
        :type="tipoActual"
        :autocomplete="autocompletar"
        :disabled="deshabilitado"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="descripcion"
        spellcheck="false"
        autocapitalize="none"
        class="min-h-[46px] w-full rounded-[7px] border bg-white px-3 py-2.5 text-[14px] text-tinta transition-colors duration-200 placeholder:text-secundario disabled:bg-fondo"
        :class="[
          error ? 'border-error' : 'border-control hover:border-tinta',
          tipo === 'password' ? 'pr-20' : '',
        ]"
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
    <p v-if="ayuda" :id="`${id}-ayuda`" class="text-[12px] text-secundario">{{ ayuda }}</p>
    <slot />
  </div>
</template>
