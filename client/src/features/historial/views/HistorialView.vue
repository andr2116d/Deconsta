<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, useId, watch } from 'vue'
import { type LocationQuery, useRoute, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { esDia } from '@/features/calendario/fechas'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import { formatearFecha, LUGARES_PAGO } from '@/features/deudas/catalogo'
import type { LugarPago } from '@/features/deudas/types'
import { useEquipoStore } from '@/features/equipo/stores/equipo'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { consultarHistorial, exportarHistorial } from '../api/historial'
import { ESTADOS_FILTRO, esEstadoFiltro } from '../catalogo'
import TarjetaHistorial from '../components/TarjetaHistorial.vue'
import type { DeudaHistorial, FiltrosHistorial, Historial } from '../types'

/**
 * El historial del espacio (gerente) o «Mis registros» (asistente: lo que registró o pagó). Los
 * filtros viven en la dirección: se comparten y sobreviven a una recarga.
 */
const route = useRoute()
const router = useRouter()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const equipo = useEquipoStore()
const notificaciones = useNotificacionesStore()

const mios = computed(() => route.name === 'mis-registros')
const gerente = computed(() => sesion.usuario?.rol === 'gerente')

const texto = (valor: unknown) => (typeof valor === 'string' && valor ? valor : undefined)
const esLugar = (valor: unknown): valor is LugarPago => LUGARES_PAGO.some((l) => l.valor === valor)

function leer(query: LocationQuery): FiltrosHistorial {
  return {
    desde: esDia(query.desde) ? query.desde : undefined,
    hasta: esDia(query.hasta) ? query.hasta : undefined,
    estado: esEstadoFiltro(query.estado) ? query.estado : undefined,
    categoria_id: texto(query.categoria_id),
    registrada_por: texto(query.registrada_por),
    pagado_por: texto(query.pagado_por),
    lugar_pago: esLugar(query.lugar_pago) ? query.lugar_pago : undefined,
    q: texto(query.q),
  }
}

const filtros = reactive<FiltrosHistorial>(leer(route.query))
const busqueda = ref(filtros.q ?? '')
const historial = ref<Historial | null>(null)
const deudas = ref<DeudaHistorial[]>([])
const cargando = ref(false)
const cargandoMas = ref(false)
const exportando = ref(false)
const fallo = ref<string | null>(null)
let consulta = 0
let espera: ReturnType<typeof setTimeout> | undefined

const hayFiltros = computed(() => Object.values(filtros).some(Boolean))
const personas = computed(() => [
  ...(sesion.usuario ? [{ id: sesion.usuario.id, nombre: `${sesion.usuario.nombres} (tú)` }] : []),
  ...(equipo.asistentes ?? []).map((a) => ({ id: a.id, nombre: `${a.nombres} ${a.apellidos}` })),
])
const categoriaDe = (id: string | null) =>
  categorias.categorias?.find((c) => c.id === id) ?? undefined
const ids = {
  q: useId(),
  estado: useId(),
  categoria: useId(),
  lugar: useId(),
  desde: useId(),
  hasta: useId(),
  registrada: useId(),
  pagado: useId(),
}

function tratar(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    sesion.olvidar()
    void router.replace({ name: 'inicio-sesion' })
    return
  }
  const campos = error instanceof ErrorApi ? Object.values(error.campos) : []
  fallo.value =
    campos[0] ?? (error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.')
}

async function cargar() {
  const numero = ++consulta
  cargando.value = true
  fallo.value = null
  try {
    const respuesta = await consultarHistorial(filtros, { mios: mios.value })
    if (numero !== consulta) return
    historial.value = respuesta
    deudas.value = respuesta.deudas
  } catch (error) {
    if (numero === consulta) tratar(error)
  } finally {
    if (numero === consulta) cargando.value = false
  }
}

async function cargarMas() {
  const cursor = historial.value?.siguiente
  if (!cursor) return
  const numero = consulta
  cargandoMas.value = true
  try {
    const respuesta = await consultarHistorial(filtros, { cursor, mios: mios.value })
    if (numero !== consulta) return
    historial.value = respuesta
    deudas.value = [...deudas.value, ...respuesta.deudas]
  } catch (error) {
    tratar(error)
  } finally {
    cargandoMas.value = false
  }
}

async function exportar() {
  exportando.value = true
  fallo.value = null
  try {
    const archivo = await exportarHistorial(filtros)
    const enlace = document.createElement('a')
    enlace.href = URL.createObjectURL(archivo)
    enlace.download = `historial-${historial.value?.desde ?? ''}-a-${historial.value?.hasta ?? ''}.csv`
    enlace.click()
    URL.revokeObjectURL(enlace.href)
  } catch (error) {
    tratar(error)
  } finally {
    exportando.value = false
  }
}

function limpiar() {
  busqueda.value = ''
  for (const clave of Object.keys(filtros) as (keyof FiltrosHistorial)[]) filtros[clave] = undefined
}

// La búsqueda espera a que se deje de escribir.
watch(busqueda, (valor) => {
  clearTimeout(espera)
  espera = setTimeout(() => (filtros.q = valor.trim() || undefined), 300)
})
watch(
  filtros,
  () => {
    const query = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v))
    void router.replace({ query })
    void cargar()
  },
  { deep: true },
)
// Un aviso nuevo (un pago, una decisión) puede cambiar lo que se ve.
watch(
  () => notificaciones.avisos,
  () => void cargar(),
)

onMounted(() => {
  void cargar()
  if (!categorias.categorias) categorias.cargar().catch(() => undefined)
  if (gerente.value && !equipo.asistentes) equipo.cargar().catch(() => undefined)
})
onBeforeUnmount(() => clearTimeout(espera))

const claseCampo =
  'mt-1 min-h-10 w-full rounded-[7px] border border-control bg-white px-3 text-[13px] hover:border-tinta'
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          {{ mios ? 'Lo que registraste y pagaste.' : 'Todo lo que pasó en tu espacio.' }}
        </h1>
        <p class="mt-2 max-w-[62ch] text-[13px] text-secundario">
          <template v-if="mios">
            Tus deudas y tus pagos, con su estado y lo que decidió tu gerente.
          </template>
          <template v-else>
            Cada deuda con sus cuotas, sus pagos y sus moras, y quién hizo qué y cuándo. Lo que
            espera tu decisión aparece resaltado.
          </template>
        </p>
      </div>
      <BaseBoton
        v-if="gerente && !mios"
        variante="secundario"
        :cargando="exportando"
        @click="exportar"
      >
        <BaseIcono nombre="archivo" class="size-4" />
        Exportar CSV
      </BaseBoton>
    </header>

    <form
      class="mb-6 grid grid-cols-1 gap-3 rounded-[14px] border border-borde bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      role="search"
      aria-label="Filtrar el historial"
      @submit.prevent
    >
      <div class="sm:col-span-2">
        <label :for="ids.q" class="text-[12px] font-bold">Buscar</label>
        <input
          :id="ids.q"
          v-model="busqueda"
          type="search"
          maxlength="80"
          placeholder="Concepto de la deuda"
          :class="claseCampo"
        />
      </div>
      <div>
        <label :for="ids.estado" class="text-[12px] font-bold">Estado</label>
        <select :id="ids.estado" v-model="filtros.estado" :class="claseCampo">
          <option :value="undefined">Todos</option>
          <optgroup v-for="grupo in ['Deuda', 'Pago']" :key="grupo" :label="grupo">
            <option
              v-for="e in ESTADOS_FILTRO.filter((e) => e.grupo === grupo)"
              :key="e.valor"
              :value="e.valor"
            >
              {{ e.etiqueta }}
            </option>
          </optgroup>
        </select>
      </div>
      <div>
        <label :for="ids.categoria" class="text-[12px] font-bold">Categoría</label>
        <select :id="ids.categoria" v-model="filtros.categoria_id" :class="claseCampo">
          <option :value="undefined">Todas</option>
          <option v-for="c in categorias.categorias ?? []" :key="c.id" :value="c.id">
            {{ c.nombre }}
          </option>
        </select>
      </div>
      <div>
        <label :for="ids.desde" class="text-[12px] font-bold">Desde</label>
        <input
          :id="ids.desde"
          v-model="filtros.desde"
          type="date"
          :max="filtros.hasta"
          :class="claseCampo"
        />
      </div>
      <div>
        <label :for="ids.hasta" class="text-[12px] font-bold">Hasta</label>
        <input
          :id="ids.hasta"
          v-model="filtros.hasta"
          type="date"
          :min="filtros.desde"
          :class="claseCampo"
        />
      </div>
      <div>
        <label :for="ids.lugar" class="text-[12px] font-bold">Dónde se paga</label>
        <select :id="ids.lugar" v-model="filtros.lugar_pago" :class="claseCampo">
          <option :value="undefined">En cualquier lugar</option>
          <option v-for="l in LUGARES_PAGO" :key="l.valor" :value="l.valor">
            {{ l.etiqueta }}
          </option>
        </select>
      </div>
      <template v-if="gerente && !mios">
        <div>
          <label :for="ids.registrada" class="text-[12px] font-bold">Registró</label>
          <select :id="ids.registrada" v-model="filtros.registrada_por" :class="claseCampo">
            <option :value="undefined">Cualquiera</option>
            <option v-for="p in personas" :key="p.id" :value="p.id">{{ p.nombre }}</option>
          </select>
        </div>
        <div>
          <label :for="ids.pagado" class="text-[12px] font-bold">Pagó</label>
          <select :id="ids.pagado" v-model="filtros.pagado_por" :class="claseCampo">
            <option :value="undefined">Cualquiera</option>
            <option v-for="p in personas" :key="p.id" :value="p.id">{{ p.nombre }}</option>
          </select>
        </div>
      </template>
      <div v-if="hayFiltros" class="flex items-end">
        <BaseBoton variante="discreto" @click="limpiar">Quitar filtros</BaseBoton>
      </div>
    </form>

    <p v-if="historial" class="mb-3 text-[12px] text-secundario" aria-live="polite">
      Del {{ formatearFecha(historial.desde) }} al {{ formatearFecha(historial.hasta) }} ·
      {{ deudas.length }}{{ historial.siguiente ? '+' : '' }}
      {{ deudas.length === 1 ? 'deuda' : 'deudas' }}
    </p>

    <BaseAviso v-if="fallo" tono="error" titulo="No pudimos cargar el historial" class="mb-4">
      {{ fallo }}
    </BaseAviso>

    <div
      v-if="cargando && !historial"
      aria-hidden="true"
      class="flex flex-col gap-3 motion-safe:animate-pulse"
    >
      <div v-for="n in 3" :key="n" class="h-[150px] rounded-[14px] border border-borde bg-white" />
    </div>

    <div
      v-else-if="historial && !deudas.length"
      class="flex flex-col items-center rounded-[14px] border border-dashed border-borde bg-white px-6 py-12 text-center"
    >
      <span
        aria-hidden="true"
        class="grid size-14 place-items-center rounded-[16px] bg-acento-suave text-acento"
      >
        <BaseIcono nombre="reloj" class="size-6" />
      </span>
      <p class="mt-5 text-[18px] font-extrabold">
        {{ hayFiltros ? 'Nada coincide con los filtros.' : 'Todavía no hay movimientos.' }}
      </p>
      <p class="mt-2 max-w-[44ch] text-[13px] text-secundario">
        {{
          hayFiltros
            ? 'Prueba con otro estado, otra fecha o quita los filtros.'
            : 'Cuando se registre una deuda o un pago, aparecerá aquí.'
        }}
      </p>
    </div>

    <template v-else-if="historial">
      <ul class="flex flex-col gap-3" :aria-busy="cargando">
        <li v-for="deuda in deudas" :key="deuda.id">
          <TarjetaHistorial
            :deuda="deuda"
            :hoy="historial.hoy"
            :gerente="gerente"
            :categoria="categoriaDe(deuda.categoria_id)"
          />
        </li>
      </ul>
      <div v-if="historial.siguiente" class="mt-5 flex justify-center">
        <BaseBoton variante="secundario" :cargando="cargandoMas" @click="cargarMas">
          Ver más
        </BaseBoton>
      </div>
    </template>
  </section>
</template>
