<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

/**
 * Ventana modal sobre <dialog>: el navegador encierra el foco y deja inerte el resto de la página.
 * Una ventana obligatoria no se cierra con Escape ni tiene botón de cerrar.
 */
const props = withDefaults(
  defineProps<{
    abierto: boolean
    titulo: string
    obligatorio?: boolean
    ancho?: 'normal' | 'amplio'
  }>(),
  { obligatorio: false, ancho: 'normal' },
)
const emit = defineEmits<{ cerrar: [] }>()

const dialogo = ref<HTMLDialogElement>()
const idTitulo = useId()

function sincronizar() {
  const elemento = dialogo.value
  if (!elemento) return
  if (props.abierto && !elemento.open) {
    // jsdom no implementa showModal; en el navegador siempre existe.
    if (typeof elemento.showModal === 'function') elemento.showModal()
    else elemento.setAttribute('open', '')
  } else if (!props.abierto && elemento.open) {
    cerrar(elemento)
  }
}

function cerrar(elemento: HTMLDialogElement) {
  if (typeof elemento.close === 'function') elemento.close()
  else elemento.removeAttribute('open')
}

function alCancelar(evento: Event) {
  if (props.obligatorio) evento.preventDefault()
}

function alCerrar() {
  // Algunos navegadores cierran aunque se cancele el Escape repetido: una ventana obligatoria
  // vuelve a abrirse mientras siga pendiente.
  if (props.abierto && props.obligatorio) sincronizar()
  else if (props.abierto) emit('cerrar')
}

onMounted(sincronizar)
watch(() => props.abierto, sincronizar, { flush: 'post' })
onBeforeUnmount(() => dialogo.value?.open && cerrar(dialogo.value))
</script>

<template>
  <dialog
    ref="dialogo"
    :aria-labelledby="idTitulo"
    class="m-auto max-h-[calc(100dvh-32px)] w-full rounded-[15px] bg-white p-0 text-tinta shadow-[0_25px_90px_#30233030] backdrop:bg-[#30233066] backdrop:backdrop-blur-[3px] open:animate-aparecer"
    :class="
      ancho === 'amplio'
        ? 'max-w-[min(640px,calc(100%-32px))]'
        : 'max-w-[min(470px,calc(100%-32px))]'
    "
    @cancel="alCancelar"
    @close="alCerrar"
  >
    <div class="flex items-center justify-between px-6 pt-5">
      <span
        v-if="$slots.icono"
        aria-hidden="true"
        class="grid size-[42px] place-items-center rounded-xl bg-acento-suave text-acento"
      >
        <slot name="icono" />
      </span>
      <button
        v-if="!obligatorio"
        type="button"
        class="ml-auto grid size-9 place-items-center rounded-lg text-secundario hover:bg-fondo hover:text-tinta"
        aria-label="Cerrar"
        @click="emit('cerrar')"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="size-[18px] fill-none stroke-current stroke-2"
          stroke-linecap="round"
        >
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      </button>
    </div>
    <div class="px-6 pt-4 pb-6">
      <h2 :id="idTitulo" class="text-[22px] leading-tight font-extrabold tracking-[-0.03em]">
        {{ titulo }}
      </h2>
      <slot />
    </div>
  </dialog>
</template>
