<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { claveNombre, SUGERENCIAS } from '../catalogo'
import DialogoCategoria from '../components/DialogoCategoria.vue'
import InsigniaCategoria from '../components/InsigniaCategoria.vue'
import { useCategoriasStore } from '../stores/categorias'
import type { Categoria, DatosCategoria } from '../types'

/**
 * Categorías del espacio para la asistente: las ve y crea nuevas. Editarlas, archivarlas y
 * reactivarlas es del gerente; el backend lo exige igual.
 */
const router = useRouter()
const sesion = useSesionStore()
const store = useCategoriasStore()

const abierta = ref(false)
const inicial = ref<DatosCategoria | null>(null)
const aviso = ref<string | null>(null)

const sugerencias = computed(() => {
  const usadas = new Set((store.categorias ?? []).map((c) => claveNombre(c.nombre)))
  return SUGERENCIAS.filter((s) => !usadas.has(claveNombre(s.nombre))).slice(0, 6)
})

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

function abrir(datos: DatosCategoria | null = null) {
  aviso.value = null
  inicial.value = datos
  abierta.value = true
}

function alGuardar(categoria: Categoria) {
  abierta.value = false
  aviso.value = `Creaste «${categoria.nombre}». Ya puedes usarla al registrar deudas.`
}

onMounted(() => {
  store.olvidar()
  store.cargar().catch((error: unknown) => {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  })
})
</script>

<template>
  <section aria-labelledby="titulo-seccion" class="max-w-[960px]">
    <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Un lugar para cada gasto.
        </h1>
        <p class="mt-2 max-w-[60ch] text-[13px] text-secundario">
          Las categorías ordenan las deudas del espacio de tu gerente. Puedes crear las que falten;
          tu gerente las administra.
        </p>
      </div>
      <BaseBoton class="shrink-0 self-start sm:self-auto" @click="abrir()">
        <BaseIcono nombre="mas" class="size-[18px]" />
        Nueva categoría
      </BaseBoton>
    </header>

    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>

    <div v-if="store.cargando && !store.categorias" class="flex justify-center py-16">
      <span
        aria-label="Cargando las categorías"
        class="size-8 animate-girar rounded-full border-2 border-acento border-t-transparent"
      />
    </div>
    <BaseAviso v-else-if="store.errorCarga && !store.categorias" tono="error">
      No pudimos cargar las categorías. Vuelve a intentarlo en unos minutos.
    </BaseAviso>
    <template v-else>
      <TransitionGroup
        v-if="store.activas.length"
        tag="ul"
        name="vista"
        class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      >
        <li
          v-for="categoria in store.activas"
          :key="categoria.id"
          class="flex items-start gap-3 rounded-[14px] border border-borde bg-white p-4"
        >
          <InsigniaCategoria :color="categoria.color" :icono="categoria.icono" />
          <div class="min-w-0">
            <h2 class="truncate text-[14px] font-extrabold">{{ categoria.nombre }}</h2>
            <p class="mt-0.5 line-clamp-2 text-[12px] text-secundario">
              {{ categoria.descripcion ?? 'Sin descripción' }}
            </p>
          </div>
        </li>
      </TransitionGroup>
      <p
        v-else
        class="rounded-2xl border border-borde bg-white px-6 py-10 text-center text-[13px] text-secundario"
      >
        Todavía no hay categorías. Lo que registres quedará en «Otros» hasta que crees alguna.
      </p>

      <section v-if="sugerencias.length" class="mt-8" aria-labelledby="titulo-sugerencias">
        <h2 id="titulo-sugerencias" class="mb-3 text-[13px] font-extrabold">Ideas para empezar</h2>
        <ul class="flex flex-wrap gap-2">
          <li v-for="sugerencia in sugerencias" :key="sugerencia.nombre">
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-borde bg-white py-1.5 pr-3.5 pl-1.5 text-[12px] font-bold transition-colors duration-200 hover:border-acento hover:text-acento"
              @click="abrir(sugerencia)"
            >
              <InsigniaCategoria
                :color="sugerencia.color"
                :icono="sugerencia.icono"
                tamano="pequeno"
              />
              {{ sugerencia.nombre }}
            </button>
          </li>
        </ul>
      </section>
    </template>

    <DialogoCategoria
      :abierto="abierta"
      :inicial="inicial"
      :puede-reactivar="false"
      @guardada="alGuardar"
      @cerrar="abierta = false"
      @sesion-terminada="sesionTerminada"
    />
  </section>
</template>
