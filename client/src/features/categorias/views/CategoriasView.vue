<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'

import { claveNombre, SUGERENCIAS } from '../catalogo'
import DialogoArchivarCategoria from '../components/DialogoArchivarCategoria.vue'
import DialogoCategoria from '../components/DialogoCategoria.vue'
import FilaCategoria from '../components/FilaCategoria.vue'
import InsigniaCategoria from '../components/InsigniaCategoria.vue'
import { useCategoriasStore } from '../stores/categorias'
import type { Categoria, DatosCategoria } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const store = useCategoriasStore()

const vista = ref<'activas' | 'archivadas'>('activas')
// Diálogo de creación o edición: abierto con una categoría (editar) o con datos iniciales.
const formulario = ref<{ categoria: Categoria | null; inicial: DatosCategoria | null } | null>(null)
const porArchivar = ref<Categoria | null>(null)
const ocupada = ref<string | null>(null)
const aviso = ref<string | null>(null)
const fallo = ref<ErrorApi | null>(null)

const lista = computed(() => (vista.value === 'activas' ? store.activas : store.archivadas))
// Sugerencias que aún no existen en el espacio (ni archivadas).
const sugerencias = computed(() => {
  const usadas = new Set((store.categorias ?? []).map((c) => claveNombre(c.nombre)))
  return SUGERENCIAS.filter((s) => !usadas.has(claveNombre(s.nombre)))
})

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

function mostrarFallo(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    sesionTerminada()
    return
  }
  fallo.value =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
}

async function cargar() {
  try {
    await store.cargar()
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  }
}

function abrir(categoria: Categoria | null = null, inicial: DatosCategoria | null = null) {
  aviso.value = null
  formulario.value = { categoria, inicial }
}

function alGuardar(categoria: Categoria, creada: boolean) {
  formulario.value = null
  vista.value = 'activas'
  aviso.value = creada
    ? `Creaste la categoría «${categoria.nombre}». Ya está disponible para todo tu equipo.`
    : `Guardaste los cambios de «${categoria.nombre}».`
}

async function reactivar(id: string) {
  formulario.value = null
  aviso.value = null
  ocupada.value = id
  try {
    const categoria = await store.reactivar(id)
    vista.value = 'activas'
    aviso.value = `Reactivaste «${categoria.nombre}». Vuelve a estar disponible para tu equipo.`
  } catch (error) {
    mostrarFallo(error)
  } finally {
    ocupada.value = null
  }
}

async function archivar(motivo: string | null) {
  const categoria = porArchivar.value
  if (!categoria) return
  ocupada.value = categoria.id
  aviso.value = null
  try {
    await store.archivar(categoria.id, motivo)
    aviso.value = `Archivaste «${categoria.nombre}». Las deudas que ya la usan la conservan.`
  } catch (error) {
    mostrarFallo(error)
  } finally {
    porArchivar.value = null
    ocupada.value = null
  }
}

onMounted(() => {
  // Nunca se ven, ni por un instante, las categorías de otra sesión.
  store.olvidar()
  void cargar()
})
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Un lugar para cada gasto.
        </h1>
        <p class="mt-2 max-w-[60ch] text-[13px] text-secundario">
          Tus categorías ordenan las deudas para filtrarlas, resumirlas y exportarlas. Las comparte
          todo tu equipo.
        </p>
      </div>
      <BaseBoton class="shrink-0 self-start sm:self-auto" @click="abrir()">
        <BaseIcono nombre="mas" class="size-[18px]" />
        Nueva categoría
      </BaseBoton>
    </header>

    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
      <div class="min-w-0">
        <div v-if="store.errorCarga && !store.categorias" class="flex flex-col items-start gap-3">
          <BaseAviso tono="error" titulo="No pudimos cargar tus categorías" class="w-full">
            {{
              store.errorCarga instanceof ErrorApi
                ? store.errorCarga.message
                : 'Ocurrió un error inesperado.'
            }}
          </BaseAviso>
          <BaseBoton variante="secundario" :cargando="store.cargando" @click="cargar">
            Reintentar
          </BaseBoton>
        </div>

        <div
          v-else-if="!store.categorias"
          aria-hidden="true"
          class="rounded-[14px] border border-borde bg-white px-5 motion-safe:animate-pulse"
        >
          <div v-for="n in 3" :key="n" class="flex items-center gap-4 border-b border-borde py-4">
            <span class="size-10 rounded-xl bg-fondo" />
            <span class="h-4 w-40 rounded bg-fondo" />
          </div>
        </div>

        <template v-else>
          <div
            class="mb-4 inline-flex rounded-[10px] bg-fondo p-1"
            role="group"
            aria-label="Mostrar categorías"
          >
            <button
              v-for="opcion in [
                { valor: 'activas', texto: 'Activas', cantidad: store.activas.length },
                { valor: 'archivadas', texto: 'Archivadas', cantidad: store.archivadas.length },
              ] as const"
              :key="opcion.valor"
              type="button"
              class="min-h-10 rounded-[8px] px-4 text-[13px] font-bold transition-colors duration-200"
              :class="
                vista === opcion.valor
                  ? 'bg-white text-tinta shadow-[0_1px_4px_#30233014]'
                  : 'text-secundario hover:text-tinta'
              "
              :aria-pressed="vista === opcion.valor"
              @click="vista = opcion.valor"
            >
              {{ opcion.texto }}
              <span class="ml-1 tabular-nums">{{ opcion.cantidad }}</span>
            </button>
          </div>

          <div
            v-if="!lista.length"
            class="flex flex-col items-center rounded-[14px] border border-dashed border-borde bg-white px-6 py-12 text-center"
          >
            <span
              aria-hidden="true"
              class="grid size-14 place-items-center rounded-[16px] bg-acento-suave text-acento motion-safe:animate-flotar"
            >
              <BaseIcono :nombre="vista === 'activas' ? 'etiqueta' : 'archivo'" class="size-6" />
            </span>
            <template v-if="vista === 'activas'">
              <p class="mt-5 text-[18px] font-extrabold">Aún no tienes categorías.</p>
              <p class="mt-2 max-w-[44ch] text-[13px] text-secundario">
                Crea las que uses o empieza con una sugerencia: agua, luz, tarjetas…
              </p>
            </template>
            <template v-else>
              <p class="mt-5 text-[18px] font-extrabold">No tienes categorías archivadas.</p>
              <p class="mt-2 max-w-[44ch] text-[13px] text-secundario">
                Al archivar una, dejará de ofrecerse en las deudas nuevas y la verás aquí.
              </p>
            </template>
          </div>

          <TransitionGroup
            v-else
            tag="ul"
            class="rounded-[14px] border border-borde bg-white px-5"
            :aria-label="vista === 'activas' ? 'Categorías activas' : 'Categorías archivadas'"
            enter-active-class="transition duration-300 ease-out"
            enter-from-class="opacity-0 -translate-y-1"
            leave-active-class="transition duration-200 ease-in"
            leave-to-class="opacity-0 -translate-x-2"
          >
            <FilaCategoria
              v-for="categoria in lista"
              :key="categoria.id"
              :categoria="categoria"
              :ocupada="ocupada === categoria.id"
              @editar="abrir(categoria)"
              @archivar="porArchivar = categoria"
              @reactivar="reactivar(categoria.id)"
            />
          </TransitionGroup>

          <section
            v-if="vista === 'activas' && sugerencias.length"
            aria-labelledby="titulo-sugerencias"
            class="mt-6"
          >
            <h2 id="titulo-sugerencias" class="text-[15px] font-extrabold">
              Sugerencias para empezar
            </h2>
            <p class="mt-1 text-[12px] text-secundario">
              Elige una para revisarla antes de crearla.
            </p>
            <ul class="mt-3 flex flex-wrap gap-2">
              <li v-for="sugerencia in sugerencias" :key="sugerencia.nombre">
                <button
                  type="button"
                  class="inline-flex min-h-11 items-center gap-2 rounded-full border border-borde bg-white py-1 pr-4 pl-1 text-[13px] font-bold transition-[border-color,transform] duration-200 hover:border-control motion-safe:hover:-translate-y-0.5"
                  @click="abrir(null, sugerencia)"
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
      </div>

      <aside class="flex flex-col gap-4 self-start">
        <div class="rounded-[14px] border border-borde bg-white p-5">
          <BaseIcono nombre="documento" class="size-6 text-acento" />
          <h2 class="mt-3 text-[15px] font-extrabold">Describe qué va en cada una.</h2>
          <p class="mt-1.5 text-[13px] text-secundario">
            Con la descripción, Deconsta podrá sugerir la categoría de cada recibo que subas. Al
            exportar las deudas, la categoría saldrá en su propia columna para filtrarla.
          </p>
        </div>
        <div class="rounded-[14px] bg-fondo p-5 text-[13px] text-secundario">
          <h2 class="text-[15px] font-extrabold text-tinta">Límite de autorización</h2>
          <p class="mt-1.5">
            Pronto podrás definir aquí el importe en soles desde el que una deuda necesita tu
            autorización.
          </p>
        </div>
      </aside>
    </div>

    <DialogoCategoria
      :abierto="formulario !== null"
      :categoria="formulario?.categoria"
      :inicial="formulario?.inicial"
      @guardada="alGuardar"
      @reactivar="reactivar"
      @cerrar="formulario = null"
      @sesion-terminada="sesionTerminada"
    />
    <DialogoArchivarCategoria
      :categoria="porArchivar"
      :enviando="ocupada !== null"
      @confirmar="archivar"
      @cancelar="porArchivar = null"
    />
    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos completar la acción"
      :etiquetas="{}"
      @cerrar="fallo = null"
      @reintentar="
        () => {
          fallo = null
          void cargar()
        }
      "
    />
  </section>
</template>
