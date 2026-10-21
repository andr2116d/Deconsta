<script setup lang="ts">
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import { useLimpiarErrores } from '@/shared/composables/useLimpiarErrores'

import {
  avisoNombre,
  COLORES,
  filtrarNombreCategoria,
  ICONOS,
  LARGO_MAXIMO_DESCRIPCION,
  LARGO_MAXIMO_NOMBRE,
  LARGO_MINIMO_NOMBRE,
} from '../catalogo'
import { useCategoriasStore } from '../stores/categorias'
import type {
  Categoria,
  CategoriaExistente,
  ColorCategoria,
  DatosCategoria,
  IconoCategoria,
} from '../types'
import InsigniaCategoria from './InsigniaCategoria.vue'

/**
 * Crea una categoría (vacía o a partir de una sugerencia) o edita una existente. Avisa antes de
 * enviar lo que puede saberse en el navegador; el backend vuelve a validar todo y decide.
 */
const props = defineProps<{
  abierto: boolean
  /** Categoría a editar; sin ella, se crea una nueva. */
  categoria?: Categoria | null
  /** Datos con los que empieza una categoría nueva (una sugerencia). */
  inicial?: DatosCategoria | null
}>()
const emit = defineEmits<{
  guardada: [categoria: Categoria, creada: boolean]
  reactivar: [id: string]
  cerrar: []
  'sesion-terminada': []
}>()

type Campo = 'nombre' | 'descripcion' | 'color' | 'icono'

const store = useCategoriasStore()
const campoNombre = ref<InstanceType<typeof BaseCampo>>()
const idDescripcion = useId()
const datos = reactive({
  nombre: '',
  descripcion: '',
  color: 'ciruela' as ColorCategoria,
  icono: 'etiqueta' as IconoCategoria,
})
const errores = reactive<Partial<Record<Campo, string>>>({})
useLimpiarErrores(datos, errores)
const enviando = ref(false)
const fallo = ref<ErrorApi | null>(null)
const existente = ref<CategoriaExistente | null>(null)

const editando = computed(() => Boolean(props.categoria))
const titulo = computed(() => (editando.value ? 'Editar categoría' : 'Nueva categoría'))
const limpiar = (texto: string) => texto.trim().split(/\s+/).join(' ')
const descripcionFinal = computed(() => limpiar(datos.descripcion) || null)

// Al editar, Guardar solo se activa con un cambio real.
const hayCambios = computed(() => {
  const actual = props.categoria
  if (!actual) return true
  return (
    limpiar(datos.nombre) !== actual.nombre ||
    descripcionFinal.value !== actual.descripcion ||
    datos.color !== actual.color ||
    datos.icono !== actual.icono
  )
})
const aviso = computed(() => avisoNombre(datos.nombre, store.categorias ?? [], props.categoria?.id))
const restantes = computed(() => LARGO_MAXIMO_DESCRIPCION - datos.descripcion.length)

function reiniciar() {
  const base = props.categoria ?? props.inicial
  datos.nombre = base?.nombre ?? ''
  datos.descripcion = base?.descripcion ?? ''
  // Un color distinto para cada categoría nueva, siguiendo la paleta.
  const colores = Object.keys(COLORES) as ColorCategoria[]
  datos.color = base?.color ?? colores[(store.categorias?.length ?? 0) % colores.length]!
  datos.icono = base?.icono ?? 'etiqueta'
  for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
  fallo.value = null
  existente.value = null
}

watch(
  () => props.abierto,
  async (abierto) => {
    if (!abierto) return
    reiniciar()
    await nextTick()
    campoNombre.value?.enfocar()
  },
  { immediate: true },
)

function validar(): boolean {
  const nombre = limpiar(datos.nombre)
  if (!nombre) errores.nombre = 'Escribe el nombre de la categoría.'
  else if (nombre.length < LARGO_MINIMO_NOMBRE) {
    errores.nombre = `Usa de ${LARGO_MINIMO_NOMBRE} a ${LARGO_MAXIMO_NOMBRE} caracteres.`
  } else if (!/\p{L}/u.test(nombre)) errores.nombre = 'Incluye al menos una letra.'
  if (errores.nombre) campoNombre.value?.enfocar()
  return !errores.nombre
}

function mostrarFallo(error: unknown) {
  const comoApi =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
  if (comoApi.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return
  }
  Object.assign(errores, comoApi.campos)
  if (comoApi.codigo === 'CATEGORIA_DUPLICADA') {
    const otra = comoApi.cuerpo.existing_category as CategoriaExistente | undefined
    existente.value = otra?.archivada ? otra : null
  }
  // Lo que no apunta a un campo (límites, conexión, sesión) se explica arriba del botón.
  if (!Object.keys(comoApi.campos).length) fallo.value = comoApi
  if (errores.nombre) campoNombre.value?.enfocar()
}

async function guardar() {
  fallo.value = null
  existente.value = null
  if (!validar() || !hayCambios.value) return
  const solicitud: DatosCategoria = {
    nombre: datos.nombre,
    descripcion: descripcionFinal.value,
    color: datos.color,
    icono: datos.icono,
  }
  enviando.value = true
  try {
    const guardada = props.categoria
      ? await store.editar(props.categoria.id, solicitud)
      : await store.crear(solicitud)
    emit('guardada', guardada, !props.categoria)
  } catch (error) {
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}

const coloresDisponibles = Object.entries(COLORES) as Array<
  [ColorCategoria, (typeof COLORES)[ColorCategoria]]
>
const iconosDisponibles = Object.entries(ICONOS) as Array<[IconoCategoria, string]>
</script>

<template>
  <BaseDialogo :abierto="abierto" :titulo="titulo" ancho="amplio" @cerrar="emit('cerrar')">
    <template #icono>
      <BaseIcono :nombre="editando ? 'lapiz' : 'mas'" class="size-5" />
    </template>
    <form class="mt-4" novalidate @submit.prevent="guardar">
      <!-- Vista previa: cómo se verá en la lista y, más adelante, en cada deuda. -->
      <div
        class="mb-5 flex items-center gap-3 rounded-[12px] bg-fondo p-3"
        aria-live="polite"
        aria-atomic="true"
      >
        <InsigniaCategoria :color="datos.color" :icono="datos.icono" tamano="grande" />
        <div class="min-w-0">
          <p class="text-[11px] font-bold tracking-wide text-secundario uppercase">Así se verá</p>
          <p class="truncate text-[15px] font-extrabold">
            {{ limpiar(datos.nombre) || 'Nombre de la categoría' }}
          </p>
        </div>
      </div>

      <BaseCampo
        ref="campoNombre"
        v-model="datos.nombre"
        etiqueta="Nombre"
        autocompletar="off"
        :maximo="LARGO_MAXIMO_NOMBRE"
        :filtro="filtrarNombreCategoria"
        :aviso="aviso"
        :error="errores.nombre"
        ayuda="Por ejemplo: Agua, Luz del local o Tarjeta Visa."
      >
        <BaseBoton
          v-if="existente"
          variante="secundario"
          class="mt-1 self-start"
          @click="emit('reactivar', existente.id)"
        >
          Reactivar la categoría archivada
        </BaseBoton>
      </BaseCampo>

      <div class="mb-5 flex flex-col gap-1.5">
        <label :for="idDescripcion" class="text-[12px] font-bold">
          Descripción <span class="font-normal text-secundario">(opcional)</span>
        </label>
        <textarea
          :id="idDescripcion"
          v-model="datos.descripcion"
          rows="2"
          :maxlength="LARGO_MAXIMO_DESCRIPCION"
          :aria-invalid="errores.descripcion ? 'true' : undefined"
          :aria-describedby="`${idDescripcion}-ayuda`"
          class="w-full resize-none rounded-[7px] border px-3 py-2.5 text-[14px] transition-colors duration-200 hover:border-tinta"
          :class="errores.descripcion ? 'border-error' : 'border-control'"
        />
        <p v-if="errores.descripcion" class="animate-aparecer text-[12px] text-error">
          {{ errores.descripcion }}
        </p>
        <p
          :id="`${idDescripcion}-ayuda`"
          class="flex justify-between gap-3 text-[12px] text-secundario"
        >
          <span>Qué recibos van aquí. Ayudará a clasificarlos automáticamente.</span>
          <span aria-hidden="true" class="shrink-0 tabular-nums">{{ restantes }}</span>
        </p>
      </div>

      <fieldset class="mb-5">
        <legend class="mb-2 text-[12px] font-bold">Color</legend>
        <div class="flex flex-wrap gap-2">
          <label
            v-for="[valor, tono] in coloresDisponibles"
            :key="valor"
            class="relative grid size-11 cursor-pointer place-items-center rounded-full border-2 transition-[border-color,transform] duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acento motion-safe:hover:scale-105"
            :class="datos.color === valor ? 'border-tinta' : 'border-transparent'"
            :title="tono.nombre"
          >
            <input v-model="datos.color" type="radio" :value="valor" class="sr-only" />
            <span class="sr-only">{{ tono.nombre }}</span>
            <span
              aria-hidden="true"
              class="grid size-8 place-items-center rounded-full"
              :style="{ backgroundColor: tono.tinta }"
            >
              <BaseIcono
                v-if="datos.color === valor"
                nombre="check"
                class="size-4 animate-aparecer text-white"
              />
            </span>
          </label>
        </div>
        <p v-if="errores.color" class="mt-1.5 text-[12px] text-error">{{ errores.color }}</p>
      </fieldset>

      <fieldset class="mb-6">
        <legend class="mb-2 text-[12px] font-bold">Ícono</legend>
        <div class="grid grid-cols-5 gap-2 sm:grid-cols-7">
          <label
            v-for="[valor, etiqueta] in iconosDisponibles"
            :key="valor"
            class="grid h-12 cursor-pointer place-items-center rounded-[10px] border transition-colors duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acento"
            :class="
              datos.icono === valor
                ? 'border-acento bg-acento-suave text-acento'
                : 'border-borde text-secundario hover:border-control hover:text-tinta'
            "
            :title="etiqueta"
          >
            <input v-model="datos.icono" type="radio" :value="valor" class="sr-only" />
            <span class="sr-only">{{ etiqueta }}</span>
            <BaseIcono :nombre="valor" class="size-5" />
          </label>
        </div>
        <p v-if="errores.icono" class="mt-1.5 text-[12px] text-error">{{ errores.icono }}</p>
      </fieldset>

      <BaseAviso v-if="fallo" tono="error" titulo="No pudimos guardar la categoría" class="mb-4">
        {{ fallo.message }}
        <template v-if="fallo.referencia"> Referencia: {{ fallo.referencia }}.</template>
      </BaseAviso>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
        <p v-if="editando && !hayCambios" class="text-[12px] text-secundario sm:mr-auto">
          Cambia algún dato para guardar.
        </p>
        <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cerrar')">
          Cancelar
        </BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando" :deshabilitado="!hayCambios">
          {{ editando ? 'Guardar cambios' : 'Crear categoría' }}
        </BaseBoton>
      </div>
    </form>
  </BaseDialogo>
</template>
