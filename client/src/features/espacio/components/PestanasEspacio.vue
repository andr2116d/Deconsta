<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { seccionesDe, textoPorRol } from '../secciones'

const props = defineProps<{ rol: Rol }>()

const route = useRoute()
const lista = ref<HTMLUListElement>()
// En pantallas angostas las pestañas se desplazan de lado: un degradado en el borde indica que
// hay más pestañas en esa dirección.
const hayAntes = ref(false)
const hayDespues = ref(false)

const pestanas = computed(() =>
  seccionesDe(props.rol, 'pestana').map((s) => ({
    nombre: s.nombre,
    icono: s.icono,
    etiqueta: textoPorRol(s.etiqueta, props.rol),
  })),
)

const mascara = computed(() => {
  if (!hayAntes.value && !hayDespues.value) return undefined
  const inicio = hayAntes.value ? 'transparent 0, #000 32px' : '#000 0'
  const fin = hayDespues.value ? '#000 calc(100% - 32px), transparent 100%' : '#000 100%'
  const degradado = `linear-gradient(to right, ${inicio}, ${fin})`
  return { maskImage: degradado, WebkitMaskImage: degradado }
})

function medir() {
  const elemento = lista.value
  if (!elemento) return
  hayAntes.value = elemento.scrollLeft > 1
  hayDespues.value = elemento.scrollLeft + elemento.clientWidth < elemento.scrollWidth - 1
}

function mostrarActiva() {
  const activa = lista.value?.querySelector<HTMLElement>('[aria-current="page"]')
  const reducir = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  // jsdom no implementa scrollIntoView.
  activa?.scrollIntoView?.({
    block: 'nearest',
    inline: 'nearest',
    behavior: reducir ? 'auto' : 'smooth',
  })
}

let observador: ResizeObserver | undefined

onMounted(() => {
  medir()
  mostrarActiva()
  if (typeof ResizeObserver !== 'undefined' && lista.value) {
    observador = new ResizeObserver(medir)
    observador.observe(lista.value)
  }
})
onBeforeUnmount(() => observador?.disconnect())

watch(
  () => route.name,
  async () => {
    await nextTick()
    mostrarActiva()
  },
)
</script>

<template>
  <nav
    :aria-label="rol === 'gerente' ? 'Secciones de gerencia' : 'Secciones de asistencia'"
    class="-mx-4 sm:-mx-6 lg:mx-0"
  >
    <ul
      ref="lista"
      class="flex h-12 gap-6 overflow-x-auto overscroll-x-contain px-4 [scrollbar-width:none] sm:px-6 lg:gap-7 lg:px-0 [&::-webkit-scrollbar]:hidden"
      :style="mascara"
      @scroll.passive="medir"
    >
      <li v-for="pestana in pestanas" :key="pestana.nombre" class="flex shrink-0">
        <RouterLink
          v-slot="{ href, navigate, isExactActive }"
          :to="{ name: pestana.nombre }"
          custom
        >
          <a
            :href="href"
            :aria-current="isExactActive ? 'page' : undefined"
            class="group relative inline-flex items-center gap-2 text-[13px] whitespace-nowrap transition-colors duration-200"
            :class="
              isExactActive
                ? 'font-extrabold text-acento'
                : 'font-semibold text-secundario hover:text-acento'
            "
            @click="navigate"
          >
            <BaseIcono :nombre="pestana.icono" class="hidden size-4 sm:block" />
            {{ pestana.etiqueta }}
            <span
              aria-hidden="true"
              class="absolute inset-x-0 bottom-0 h-[3px] origin-bottom rounded-t-[3px] bg-acento transition-transform duration-200 ease-out"
              :class="isExactActive ? 'scale-y-100' : 'scale-y-0 group-hover:scale-y-50'"
            />
          </a>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>
