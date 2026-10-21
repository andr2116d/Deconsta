<script setup lang="ts">
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'

import type { Rol } from '@/features/acceso/types'
import DialogoCategoria from '@/features/categorias/components/DialogoCategoria.vue'
import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import type { Categoria, DatosCategoria, IconoCategoria } from '@/features/categorias/types'
import CampoDocumentoTitular from '@/features/reglas/components/CampoDocumentoTitular.vue'
import { avisoImporte, filtrarImporte, normalizarImporte } from '@/features/reglas/importes'
import type { TipoDocumentoTitular } from '@/features/reglas/types'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { registrarDeuda } from '../api/deudas'
import { LUGARES_PAGO, TIPOS_DOCUMENTO } from '../catalogo'
import { cuotasPropuestas } from '../cuotas'
import type { CuotaNueva, Documento, LugarPago, RegistroDeuda } from '../types'
import TablaCuotas from './TablaCuotas.vue'

/**
 * Datos de la deuda, propuestos por el análisis del documento. Todo se puede corregir: el sistema
 * puede equivocarse. El backend vuelve a validar cada campo y aplica las reglas del espacio con lo
 * que dice el documento, no con lo corregido.
 */
const props = defineProps<{ documento: Documento; rol: Rol }>()
const emit = defineEmits<{ registrada: [registro: RegistroDeuda]; 'sesion-terminada': [] }>()

const ICONOS_TIPO: Partial<Record<string, IconoCategoria>> = {
  papeleta: 'transporte',
  tributo: 'impuestos',
  cronograma: 'banco',
  estado_cuenta: 'tarjeta',
  factura: 'impuestos',
}

const categorias = useCategoriasStore()
const propuesta = props.documento.propuesta
const idLugar = useId()
const idCategoria = useId()
const idCuotas = useId()
const raiz = ref<HTMLFormElement>()

const iniciales = cuotasPropuestas(propuesta)
const datos = reactive({
  concepto: propuesta?.concepto ?? '',
  categoria_id: '',
  lugares_pago: (propuesta?.lugar_pago ? [propuesta.lugar_pago] : []) as LugarPago[],
  en_cuotas: propuesta?.tipo === 'cronograma' || iniciales.length > 1,
  importe: iniciales[0]?.importe ?? '',
  vence_el: iniciales[0]?.vence_el ?? '',
  cuotas: iniciales as CuotaNueva[],
  titular_nombre: propuesta?.titular_nombre ?? '',
  titular_tipo: (propuesta?.titular_tipo_documento ?? null) as TipoDocumentoTitular | null,
  titular_numero: propuesta?.titular_numero_documento ?? '',
  codigo_pago: propuesta?.codigo_pago ?? '',
})
const errores = ref<Record<string, string>>({})
const fallo = ref<ErrorApi | null>(null)
const enviando = ref(false)
const sugerenciaDescartada = ref(false)
const creandoCategoria = ref(false)

// La categoría que propuso el análisis, si existe en el espacio.
watch(
  () => categorias.activas,
  (activas) => {
    if (datos.categoria_id || !propuesta?.categoria) return
    datos.categoria_id = activas.find((c) => c.nombre === propuesta.categoria)?.id ?? ''
  },
  { immediate: true },
)

const sugerencia = computed(() => {
  const nombre = propuesta?.categoria_nueva
  if (!nombre || datos.categoria_id || sugerenciaDescartada.value) return null
  const existente = categorias.activas.find(
    (c) => c.nombre.localeCompare(nombre, 'es', { sensitivity: 'base' }) === 0,
  )
  return existente ? null : nombre
})
const inicialCategoria = computed<DatosCategoria | null>(() =>
  sugerencia.value
    ? {
        nombre: sugerencia.value,
        descripcion: null,
        color: 'ciruela',
        icono: ICONOS_TIPO[propuesta?.tipo ?? ''] ?? 'etiqueta',
      }
    : null,
)
// «tu recibo de servicio de Hidrandina S.A.», sin repetir el punto final del emisor.
const origen = computed(() => {
  if (!propuesta) return null
  const tipo = TIPOS_DOCUMENTO[propuesta.tipo].toLowerCase()
  const emisor = propuesta.emisor?.replace(/\.+$/, '')
  return emisor ? `tu ${tipo} de ${emisor}` : `tu ${tipo}`
})
const categoriaElegida = computed(() => categorias.activas.find((c) => c.id === datos.categoria_id))

// Solo orienta: el backend decide si la deuda espera autorización.
const corregido = computed(() => {
  if (!propuesta) return false
  const importe = normalizarImporte(datos.importe)
  const importeCambio = !datos.en_cuotas && propuesta.importe && importe !== propuesta.importe
  const codigo = (v: string | null) => (v ?? '').replace(/[^0-9a-z]/gi, '').toUpperCase()
  const codigoCambio =
    propuesta.codigo_pago && codigo(datos.codigo_pago) !== codigo(propuesta.codigo_pago)
  return Boolean(importeCambio || codigoCambio)
})

function alCrearCategoria(categoria: Categoria) {
  creandoCategoria.value = false
  datos.categoria_id = categoria.id
}

async function reactivarCategoria(id: string) {
  try {
    alCrearCategoria(await categorias.reactivar(id))
  } catch (error) {
    creandoCategoria.value = false
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') emit('sesion-terminada')
  }
}

function limpiar(campo: string) {
  if (errores.value[campo]) {
    errores.value = Object.fromEntries(
      Object.entries(errores.value).filter(([clave]) => clave !== campo),
    )
  }
}
watch(
  () => ({ ...datos }),
  (actual, anterior) => {
    for (const campo of Object.keys(actual) as (keyof typeof datos)[]) {
      if (actual[campo] !== anterior[campo]) limpiar(campo)
    }
  },
)

/** Con una sola cuota, sus errores se muestran junto al importe y al vencimiento. */
function erroresDeCampos(campos: Record<string, string>): Record<string, string> {
  if (datos.en_cuotas) return campos
  const { 'cuotas.0.importe': importe, 'cuotas.0.vence_el': vence, cuotas, ...resto } = campos
  return {
    ...resto,
    ...(importe || cuotas ? { importe: importe ?? cuotas ?? '' } : {}),
    ...(vence ? { vence_el: vence } : {}),
  }
}

async function enfocarError() {
  await nextTick()
  raiz.value?.querySelector<HTMLElement>('[aria-invalid="true"], [data-error]')?.focus()
}

async function enviar() {
  if (enviando.value) return
  enviando.value = true
  fallo.value = null
  errores.value = {}
  const cuotas = (
    datos.en_cuotas ? datos.cuotas : [{ vence_el: datos.vence_el, importe: datos.importe }]
  ).map((c) => ({ vence_el: c.vence_el, importe: normalizarImporte(c.importe) }))
  try {
    const registro = await registrarDeuda({
      documento_id: props.documento.id,
      concepto: datos.concepto,
      categoria_id: datos.categoria_id || null,
      lugares_pago: datos.lugares_pago,
      cuotas,
      titular_nombre: datos.titular_nombre || null,
      titular_tipo_documento: datos.titular_tipo,
      titular_numero_documento: datos.titular_tipo ? datos.titular_numero : null,
      codigo_pago: datos.codigo_pago || null,
    })
    emit('registrada', registro)
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    const api =
      error instanceof ErrorApi
        ? error
        : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
    errores.value = erroresDeCampos(api.campos)
    fallo.value = api
    await enfocarError()
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <form ref="raiz" novalidate @submit.prevent="enviar">
    <section class="border-b border-borde pb-5">
      <h2 class="text-[14px] font-extrabold">Datos de la deuda</h2>
      <p class="mt-1 mb-4 text-[12px] text-secundario">
        {{
          origen
            ? `Los llenamos desde ${origen}. Revísalos: el sistema puede equivocarse.`
            : 'No pudimos proponer los datos: complétalos mirando el documento.'
        }}
      </p>

      <BaseCampo
        v-model="datos.concepto"
        etiqueta="Concepto"
        :maximo="80"
        capitalizar
        :error="errores.concepto"
        ayuda="Cómo la reconocerás en tu agenda, por ejemplo «Luz de la casa · setiembre»."
      />

      <label class="mb-4 flex items-start gap-2.5 text-[13px]">
        <input
          v-model="datos.en_cuotas"
          type="checkbox"
          class="mt-0.5 size-[17px] shrink-0 accent-[var(--color-acento)]"
          :aria-controls="idCuotas"
        />
        <span>
          <strong>Se paga en cuotas</strong>
          <small class="block text-[12px] text-secundario">
            Para préstamos y contratos: cada cuota con su fecha y su importe, aunque alguna cambie.
          </small>
        </span>
      </label>

      <div :id="idCuotas">
        <Transition name="vista" mode="out-in">
          <TablaCuotas v-if="datos.en_cuotas" v-model="datos.cuotas" :errores="errores" />
          <div v-else class="grid gap-x-4 sm:grid-cols-2">
            <BaseCampo
              :model-value="datos.importe"
              etiqueta="Importe (S/)"
              modo-entrada="decimal"
              :filtro="filtrarImporte"
              :error="errores.importe"
              :aviso="avisoImporte(datos.importe)"
              @update:model-value="datos.importe = $event"
            />
            <div class="mb-4 flex flex-col gap-1.5">
              <label for="vence-el" class="text-[12px] font-bold">Vence el</label>
              <input
                id="vence-el"
                v-model="datos.vence_el"
                type="date"
                :aria-invalid="errores.vence_el ? 'true' : undefined"
                class="min-h-[46px] w-full rounded-[7px] border bg-white px-3 text-[14px] transition-colors duration-200"
                :class="errores.vence_el ? 'border-error' : 'border-control hover:border-tinta'"
              />
              <p v-if="errores.vence_el" class="animate-aparecer text-[12px] text-error">
                {{ errores.vence_el }}
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </section>

    <section class="border-b border-borde py-5">
      <h2 class="text-[14px] font-extrabold">Titular y código de pago</h2>
      <p class="mt-1 mb-4 text-[12px] text-secundario">Tal como figuran en el documento.</p>
      <BaseCampo
        v-model="datos.titular_nombre"
        etiqueta="Titular del documento"
        :maximo="120"
        :error="errores.titular_nombre"
      />
      <CampoDocumentoTitular
        v-model:tipo="datos.titular_tipo"
        v-model:numero="datos.titular_numero"
        :error="errores.titular_numero_documento"
        :error-tipo="errores.titular_tipo_documento"
      />
      <BaseCampo
        v-model="datos.codigo_pago"
        etiqueta="Código de pago o suministro"
        :maximo="40"
        :error="errores.codigo_pago"
        ayuda="Lo que se da al pagar: suministro, código de cliente o número de crédito."
      />
      <BaseAviso v-if="corregido && rol === 'asistente'" tono="aviso" class="mt-1">
        Cambiaste el importe o el código de pago del documento. Si los envías así, tu gerente deberá
        autorizar esta deuda antes de pagarla.
      </BaseAviso>
    </section>

    <section class="border-b border-borde py-5">
      <h2 class="text-[14px] font-extrabold">En tu espacio</h2>
      <div class="mt-3 mb-4 flex flex-col gap-1.5">
        <label :for="idCategoria" class="text-[12px] font-bold">Categoría</label>
        <div class="flex items-center gap-3">
          <InsigniaCategoria
            v-if="categoriaElegida"
            :icono="categoriaElegida.icono"
            :color="categoriaElegida.color"
          />
          <select
            :id="idCategoria"
            v-model="datos.categoria_id"
            :aria-invalid="errores.categoria_id ? 'true' : undefined"
            class="min-h-[46px] w-full rounded-[7px] border bg-white px-3 text-[14px]"
            :class="errores.categoria_id ? 'border-error' : 'border-control hover:border-tinta'"
          >
            <option value="">Otros (sin categoría)</option>
            <option
              v-for="categoria in categorias.activas"
              :key="categoria.id"
              :value="categoria.id"
            >
              {{ categoria.nombre }}
            </option>
          </select>
        </div>
        <p v-if="errores.categoria_id" class="text-[12px] text-error">{{ errores.categoria_id }}</p>
      </div>

      <Transition name="vista">
        <div
          v-if="sugerencia"
          class="mb-4 flex flex-col gap-3 rounded-lg bg-rosa p-3.5 text-[13px] text-ciruela sm:flex-row sm:items-center"
        >
          <BaseIcono nombre="destello" class="size-[18px] shrink-0" />
          <p class="flex-1 leading-snug">
            <strong class="block">
              Parece {{ TIPOS_DOCUMENTO[propuesta?.tipo ?? 'otro'].toLowerCase() }}.
            </strong>
            Crea la categoría «{{ sugerencia }}» para ordenarla mejor, o déjala en Otros.
          </p>
          <div class="flex shrink-0 gap-2">
            <BaseBoton variante="secundario" @click="sugerenciaDescartada = true">Omitir</BaseBoton>
            <BaseBoton @click="creandoCategoria = true">Crear categoría</BaseBoton>
          </div>
        </div>
      </Transition>

      <fieldset>
        <legend :id="idLugar" class="text-[12px] font-bold">¿Dónde se puede pagar?</legend>
        <p class="mt-0.5 mb-2 text-[12px] text-secundario">
          Marca todos los que acepta la empresa: el voucher del pago deberá ser de uno de ellos.
        </p>
        <div class="grid gap-2 sm:grid-cols-2" :data-error="errores.lugares_pago ? '' : undefined">
          <label
            v-for="lugar in LUGARES_PAGO"
            :key="lugar.valor"
            class="flex cursor-pointer items-center gap-3 rounded-[10px] border p-3 transition-colors duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acento"
            :class="
              datos.lugares_pago.includes(lugar.valor)
                ? 'border-acento bg-acento-suave'
                : errores.lugares_pago
                  ? 'border-error bg-white'
                  : 'border-borde bg-white hover:border-control'
            "
          >
            <input
              v-model="datos.lugares_pago"
              type="checkbox"
              name="lugares_pago"
              :value="lugar.valor"
              class="sr-only"
            />
            <span
              aria-hidden="true"
              class="grid size-9 shrink-0 place-items-center rounded-lg text-acento"
              :class="datos.lugares_pago.includes(lugar.valor) ? 'bg-white' : 'bg-fondo'"
            >
              <BaseIcono :nombre="lugar.icono" class="size-[18px]" />
            </span>
            <span class="min-w-0 flex-1">
              <strong class="block text-[13px]">{{ lugar.etiqueta }}</strong>
              <small class="block text-[11px] text-secundario">{{ lugar.detalle }}</small>
            </span>
            <BaseIcono
              v-if="datos.lugares_pago.includes(lugar.valor)"
              nombre="check"
              class="size-4 animate-aparecer text-acento"
            />
          </label>
        </div>
        <p v-if="errores.lugares_pago" class="mt-1.5 text-[12px] text-error">
          {{ errores.lugares_pago }}
        </p>
      </fieldset>
    </section>

    <div class="pt-5">
      <BaseAviso
        v-if="fallo && !Object.keys(errores).length"
        tono="error"
        class="mb-4"
        titulo="No registramos la deuda"
      >
        {{ fallo.message }}
      </BaseAviso>
      <BaseAviso v-else-if="fallo" tono="error" class="mb-4">{{ fallo.message }}</BaseAviso>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-[12px] text-secundario">
          {{
            rol === 'gerente'
              ? 'Quedará registrada a tu nombre, sin esperar autorización.'
              : 'Tu gerente recibirá un aviso y podrá revisarla.'
          }}
        </p>
        <BaseBoton tipo="submit" :cargando="enviando">
          Registrar deuda
          <BaseIcono nombre="derecha" class="size-4" />
        </BaseBoton>
      </div>
    </div>

    <DialogoCategoria
      :abierto="creandoCategoria"
      :inicial="inicialCategoria"
      :puede-reactivar="rol === 'gerente'"
      @guardada="alCrearCategoria"
      @reactivar="reactivarCategoria"
      @cerrar="creandoCategoria = false"
      @sesion-terminada="emit('sesion-terminada')"
    />
  </form>
</template>
