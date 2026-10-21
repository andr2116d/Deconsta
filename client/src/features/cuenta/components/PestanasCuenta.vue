<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import { pestanasCuenta } from '@/features/espacio/secciones'

// Pestañas de «Mi cuenta». Cada una es una ruta: se pueden compartir y el navegador vuelve atrás
// entre ellas. Cambiar de pestaña no recarga los datos de la cuenta.
const props = defineProps<{ rol: Rol }>()

const pestanas = computed(() => pestanasCuenta().filter((s) => s.roles.includes(props.rol)))

// En pantallas angostas las pestañas se desplazan de lado: la activa siempre queda a la vista.
const route = useRoute()
const lista = ref<HTMLUListElement>()

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

onMounted(mostrarActiva)
watch(
  () => route.name,
  async () => {
    await nextTick()
    mostrarActiva()
  },
)
</script>

<template>
  <nav aria-label="Secciones de Mi cuenta" class="-mx-4 mb-6 sm:mx-0 sm:mb-8">
    <ul
      ref="lista"
      class="flex gap-6 overflow-x-auto overscroll-x-contain border-b border-borde px-4 [scrollbar-width:none] sm:gap-7 sm:px-0 [&::-webkit-scrollbar]:hidden"
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
            class="group relative inline-flex min-h-11 items-center text-[13px] whitespace-nowrap transition-colors duration-200"
            :class="
              isExactActive
                ? 'font-extrabold text-acento'
                : 'font-semibold text-secundario hover:text-acento'
            "
            @click="navigate"
          >
            {{ pestana.pestanaCuenta }}
            <span
              aria-hidden="true"
              class="absolute inset-x-0 -bottom-px h-[2px] origin-bottom rounded-t-[2px] bg-acento transition-transform duration-200 ease-out"
              :class="isExactActive ? 'scale-y-100' : 'scale-y-0 group-hover:scale-y-50'"
            />
          </a>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>
