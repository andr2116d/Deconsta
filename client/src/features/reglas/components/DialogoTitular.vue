<script setup lang="ts">
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import { useLimpiarErrores } from '@/shared/composables/useLimpiarErrores'

import { useReglasStore } from '../stores/reglas'
import type { Titular, TipoDocumentoTitular } from '../types'
import CampoDocumentoTitular from './CampoDocumentoTitular.vue'

/**
 * Agrega un titular autorizado o edita su nombre y su relación. El documento no se edita: se quita
 * el titular y se agrega de nuevo. Avisa antes de enviar lo que puede saberse en el navegador; el
 * backend valida todo y decide.
 */
const props = defineProps<{ abierto: boolean; titular?: Titular | null }>()
const emit = defineEmits<{
  guardado: [titular: Titular, agregado: boolean]
  cerrar: []
  'sesion-terminada': []
}>()

type Campo =
  'nombre' | 'relacion' | 'tipo_documento' | 'numero_documento' | 'autorizacion_declarada'

const ETIQUETAS_TIPO = { dni: 'DNI', ce: 'Carné de extranjería', ruc: 'RUC' }
const LONGITUDES = { dni: [8, 8], ce: [9, 12], ruc: [11, 11] } as const

const store = useReglasStore()
const campoNombre = ref<InstanceType<typeof BaseCampo>>()
const idAutorizacion = useId()
const datos = reactive({
  nombre: '',
  relacion: '',
  tipo_documento: null as TipoDocumentoTitular | null,
  numero_documento: '',
  autorizacion_declarada: false,
})
const errores = reactive<Partial<Record<Campo, string>>>({})
useLimpiarErrores(datos, errores)
const enviando = ref(false)
const fallo = ref<ErrorApi | null>(null)

const editando = computed(() => Boolean(props.titular))
const limpiar = (texto: string) => texto.trim().split(/\s+/).join(' ')
const hayCambios = computed(() => {
  const actual = props.titular
  if (!actual) return true
  return (
    limpiar(datos.nombre) !== actual.nombre || (limpiar(datos.relacion) || null) !== actual.relacion
  )
})

watch(
  () => props.abierto,
  async (abierto) => {
    if (!abierto) return
    datos.nombre = props.titular?.nombre ?? ''
    datos.relacion = props.titular?.relacion ?? ''
    datos.tipo_documento = null
    datos.numero_documento = ''
    datos.autorizacion_declarada = false
    for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
    fallo.value = null
    await nextTick()
    campoNombre.value?.enfocar()
  },
  { immediate: true },
)

function validar(): boolean {
  const nombre = limpiar(datos.nombre)
  if (!nombre) errores.nombre = 'Escribe el nombre como aparece en sus recibos.'
  else if (nombre.split(' ').filter((p) => p.length > 1).length < 2) {
    errores.nombre = 'Escribe al menos un nombre y un apellido, o la razón social completa.'
  }
  if (!editando.value) {
    const tipo = datos.tipo_documento
    if (tipo) {
      const [minimo, maximo] = LONGITUDES[tipo]
      const largo = datos.numero_documento.length
      if (!largo)
        errores.numero_documento = 'Escribe el número de documento o elige «Sin documento».'
      else if (largo < minimo || largo > maximo) {
        errores.numero_documento = `Revisa el número: el ${ETIQUETAS_TIPO[tipo]} no está completo.`
      }
    }
    if (!datos.autorizacion_declarada) {
      errores.autorizacion_declarada =
        'Confirma que esta persona te autorizó a registrar sus datos en Deconsta.'
    }
  }
  if (errores.nombre) campoNombre.value?.enfocar()
  return Object.keys(errores).length === 0
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
  // Lo que no apunta a un campo (tope de titulares, conexión) se explica arriba del botón.
  if (!Object.keys(comoApi.campos).length) fallo.value = comoApi
  if (errores.nombre) campoNombre.value?.enfocar()
}

async function guardar() {
  fallo.value = null
  if (!validar() || !hayCambios.value) return
  enviando.value = true
  const relacion = limpiar(datos.relacion) || null
  try {
    const guardado = props.titular
      ? await store.editarTitular(props.titular.id, { nombre: datos.nombre, relacion })
      : await store.agregarTitular({
          nombre: datos.nombre,
          relacion,
          tipo_documento: datos.tipo_documento,
          numero_documento: datos.tipo_documento ? datos.numero_documento : null,
          autorizacion_declarada: datos.autorizacion_declarada,
        })
    emit('guardado', guardado, !props.titular)
  } catch (error) {
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <BaseDialogo
    :abierto="abierto"
    :titulo="editando ? 'Editar titular' : 'Agregar un titular autorizado'"
    ancho="amplio"
    @cerrar="emit('cerrar')"
  >
    <template #icono>
      <BaseIcono :nombre="editando ? 'lapiz' : 'persona'" class="size-5" />
    </template>
    <p v-if="!editando" class="mt-2 text-[13px] text-secundario">
      Sus recibos no pedirán tu autorización por estar a otro nombre. El límite de importe se sigue
      aplicando.
    </p>
    <form class="mt-5" novalidate @submit.prevent="guardar">
      <BaseCampo
        ref="campoNombre"
        v-model="datos.nombre"
        etiqueta="Nombre completo o razón social"
        autocompletar="off"
        capitalizar
        :maximo="120"
        :error="errores.nombre"
        ayuda="Como aparece en sus recibos, por ejemplo «Ruiz Soto María» o «Inversiones Ruiz S.A.C.»."
      />
      <BaseCampo
        v-model="datos.relacion"
        etiqueta="Relación contigo (opcional)"
        autocompletar="off"
        :maximo="40"
        :error="errores.relacion"
        ayuda="Por ejemplo: Esposa, Mamá o Mi empresa. Así la reconocerás en cada deuda."
      />

      <CampoDocumentoTitular
        v-if="!editando"
        v-model:tipo="datos.tipo_documento"
        v-model:numero="datos.numero_documento"
        :error="errores.numero_documento"
        :error-tipo="errores.tipo_documento"
      />
      <p v-else class="mb-4 rounded-[10px] bg-fondo p-3 text-[13px] text-secundario">
        <template v-if="titular?.tipo_documento">
          {{ ETIQUETAS_TIPO[titular.tipo_documento] }}
          <strong class="text-tinta">{{ titular.documento }}</strong
          >.
        </template>
        <template v-else>Sin documento.</template>
        Para cambiar el documento, quita este titular y agrégalo de nuevo.
      </p>

      <div v-if="!editando" class="mb-5">
        <label
          :for="idAutorizacion"
          class="flex cursor-pointer items-start gap-3 rounded-[10px] border p-3 text-[13px] transition-colors duration-200"
          :class="
            errores.autorizacion_declarada
              ? 'border-error bg-error-fondo'
              : datos.autorizacion_declarada
                ? 'border-acento bg-acento-suave'
                : 'border-borde hover:border-control'
          "
        >
          <input
            :id="idAutorizacion"
            v-model="datos.autorizacion_declarada"
            type="checkbox"
            class="mt-0.5 size-4 shrink-0 accent-[var(--color-acento)]"
            :aria-invalid="errores.autorizacion_declarada ? 'true' : undefined"
            :aria-describedby="`${idAutorizacion}-detalle`"
          />
          <span>
            <strong class="block">Esta persona me autorizó a registrar sus datos.</strong>
            <span :id="`${idAutorizacion}-detalle`" class="text-[12px] text-secundario">
              Su nombre y su documento se guardan cifrados y solo sirven para reconocer sus recibos
              (Ley 29733 de Protección de Datos Personales).
            </span>
          </span>
        </label>
        <p v-if="errores.autorizacion_declarada" class="mt-1.5 text-[12px] text-error">
          {{ errores.autorizacion_declarada }}
        </p>
      </div>

      <BaseAviso v-if="fallo" tono="error" titulo="No pudimos guardar el titular" class="mb-4">
        {{ fallo.message }}
      </BaseAviso>

      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
        <p v-if="editando && !hayCambios" class="text-[12px] text-secundario sm:mr-auto">
          Cambia algún dato para guardar.
        </p>
        <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cerrar')">
          Cancelar
        </BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando" :deshabilitado="!hayCambios">
          {{ editando ? 'Guardar cambios' : 'Agregar titular' }}
        </BaseBoton>
      </div>
    </form>
  </BaseDialogo>
</template>
