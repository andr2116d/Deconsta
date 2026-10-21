<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import CampoDocumento from '@/shared/components/CampoDocumento.vue'
import {
  avisoCelular,
  avisoCorreo,
  filtrarCelular,
  filtrarCorreo,
  filtrarNombre,
} from '@/shared/validaciones/persona'

import { camposCambiados, datosDe, requiereContrasena } from '../datos'
import { useCuentaStore } from '../stores/cuenta'
import type { Cuenta, DatosEditables, TipoDocumento } from '../types'
import DialogoCambioDocumento from './DialogoCambioDocumento.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'

const props = defineProps<{ cuenta: Cuenta }>()
const emit = defineEmits<{ 'sesion-terminada': [] }>()

type Campo = keyof DatosEditables | 'contrasena_actual'

const ETIQUETAS: Record<Campo, string> = {
  nombres: 'Nombres',
  apellidos: 'Apellidos',
  correo: 'Correo',
  telefono: 'Celular',
  tipo_documento: 'Tipo de documento',
  numero_documento: 'Número de documento',
  nombre_recibos: 'Nombre como figura en tus recibos',
  contrasena_actual: 'Contraseña actual',
}
const DOCUMENTO_FIJO =
  'Tu documento identifica a la persona titular de la cuenta y no se puede cambiar.'
const CONTRASENA_REQUERIDA = 'Confirma este cambio con tu contraseña actual.'
const ERROR_INESPERADO = 'Ocurrió un error inesperado. Inténtalo de nuevo.'

const store = useCuentaStore()
const formulario = ref<HTMLFormElement>()

interface Formulario {
  nombres: string
  apellidos: string
  correo: string
  telefono: string
  tipo_documento: TipoDocumento
  numero_documento: string
  nombre_recibos: string
}

const desde = (cuenta: Cuenta): Formulario => ({
  nombres: cuenta.nombres,
  apellidos: cuenta.apellidos,
  correo: cuenta.correo,
  telefono: cuenta.telefono ?? '',
  tipo_documento: cuenta.tipo_documento,
  numero_documento: cuenta.numero_documento,
  nombre_recibos: cuenta.nombre_recibos ?? '',
})

const datos = reactive<Formulario>(desde(props.cuenta))
const contrasena = ref('')
const errores = reactive<Partial<Record<Campo, string>>>({})
const enviando = ref(false)
const guardado = ref(false)
const fallo = ref<ErrorApi | null>(null)
const dialogoDocumento = ref<'inicio' | 'final' | null>(null)
// La persona pasó las advertencias al elegir el carné: el backend exige que lo confirme.
const documentoConfirmado = ref(false)

const esGerente = computed(() => props.cuenta.rol === 'gerente')
const original = computed(() => datosDe(props.cuenta))
const actuales = computed<DatosEditables>(() => ({
  ...datos,
  telefono: datos.telefono || null,
  nombre_recibos: esGerente.value ? datos.nombre_recibos || null : null,
}))
// Solo cuenta lo que cambia de verdad: un espacio o una mayúscula de más no activan «Guardar».
const cambios = computed(() => camposCambiados(original.value, actuales.value))
const hayCambios = computed(() => cambios.value.length > 0)
const pideContrasena = computed(() => requiereContrasena(cambios.value))
const cambiaTipo = computed(() => datos.tipo_documento !== props.cuenta.tipo_documento)
const numeroBloqueado = computed(
  () => !cambiaTipo.value && cambios.value.includes('numero_documento'),
)
const puedeGuardar = computed(() => hayCambios.value && !numeroBloqueado.value)

const errorNumero = computed(() =>
  numeroBloqueado.value ? DOCUMENTO_FIJO : errores.numero_documento,
)
const ayudaCargo = computed(() =>
  esGerente.value
    ? 'Se registró al crear tu cuenta y no se edita desde aquí.'
    : 'Lo asigna tu gerente y no se edita desde aquí.',
)
const resumen = computed(() => {
  if (!hayCambios.value) return 'Sin cambios por guardar.'
  const total = cambios.value.length
  return `${total} ${total === 1 ? 'cambio' : 'cambios'} sin guardar.`
})

function reiniciar(cuenta: Cuenta) {
  Object.assign(datos, desde(cuenta))
  contrasena.value = ''
  documentoConfirmado.value = false
  for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
}

// Al guardar llegan los datos normalizados por el backend: el formulario parte de ellos.
watch(() => props.cuenta, reiniciar)
// El aviso de guardado se va en cuanto la persona vuelve a editar.
watch(hayCambios, (hay) => {
  if (hay) guardado.value = false
})

// Volver al tipo guardado restaura el documento; pasar a carné espera a las advertencias (mientras
// tanto, el selector sigue en DNI).
const tipoDocumento = computed<TipoDocumento>({
  get: () => datos.tipo_documento,
  set: (tipo) => {
    if (tipo === props.cuenta.tipo_documento) {
      datos.tipo_documento = tipo
      datos.numero_documento = props.cuenta.numero_documento
      documentoConfirmado.value = false
    } else {
      dialogoDocumento.value = 'inicio'
    }
  },
})

async function confirmarDocumento() {
  if (dialogoDocumento.value === 'final') {
    dialogoDocumento.value = null
    await enviar()
    return
  }
  dialogoDocumento.value = null
  datos.tipo_documento = 'ce'
  datos.numero_documento = ''
  documentoConfirmado.value = true
  await nextTick()
  formulario.value
    ?.querySelector<HTMLInputElement>('[data-campo="numero_documento"] input')
    ?.focus()
}

function descartar() {
  reiniciar(props.cuenta)
}

async function enfocarPrimerError() {
  await nextTick()
  formulario.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

function mostrarFallo(error: unknown) {
  const comoApi =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: ERROR_INESPERADO })
  if (comoApi.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return
  }
  Object.assign(errores, comoApi.campos)
  if (comoApi.codigo === 'CONTRASENA_ACTUAL_INCORRECTA') contrasena.value = ''
  fallo.value = comoApi
}

function cerrarFallo() {
  fallo.value = null
  enfocarPrimerError()
}

async function guardar() {
  if (!puedeGuardar.value || enviando.value) return
  for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
  if (pideContrasena.value && !contrasena.value) {
    errores.contrasena_actual = CONTRASENA_REQUERIDA
    enfocarPrimerError()
    return
  }
  if (cambiaTipo.value && !actuales.value.numero_documento.trim()) {
    errores.numero_documento = 'Escribe el número de tu carné de extranjería.'
    enfocarPrimerError()
    return
  }
  // Última advertencia antes de cambiar el documento.
  if (cambiaTipo.value) {
    dialogoDocumento.value = 'final'
    return
  }
  await enviar()
}

async function enviar() {
  fallo.value = null
  enviando.value = true
  try {
    await store.guardarDatos({
      ...actuales.value,
      contrasena_actual: pideContrasena.value ? contrasena.value : undefined,
      confirmar_cambio_documento: cambiaTipo.value && documentoConfirmado.value,
    })
    guardado.value = true
  } catch (error) {
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <form ref="formulario" novalidate :aria-busy="enviando" @submit.prevent="guardar">
    <div class="grid gap-x-5 sm:grid-cols-2">
      <BaseCampo
        v-model="datos.nombres"
        etiqueta="Nombres"
        autocompletar="given-name"
        capitalizar
        :maximo="80"
        :filtro="filtrarNombre"
        :error="errores.nombres"
      />
      <BaseCampo
        v-model="datos.apellidos"
        etiqueta="Apellidos"
        autocompletar="family-name"
        capitalizar
        :maximo="80"
        :filtro="filtrarNombre"
        :error="errores.apellidos"
      />
      <BaseCampo
        v-model="datos.correo"
        etiqueta="Correo"
        tipo="email"
        autocompletar="email"
        modo-entrada="email"
        :maximo="254"
        :filtro="filtrarCorreo"
        :aviso="avisoCorreo(datos.correo)"
        :error="errores.correo"
      />
      <BaseCampo
        v-model="datos.telefono"
        etiqueta="Celular"
        tipo="tel"
        autocompletar="tel-national"
        modo-entrada="numeric"
        prefijo="+51"
        ayuda="Opcional. 9 dígitos, empieza con 9."
        :filtro="filtrarCelular"
        :aviso="avisoCelular(datos.telefono)"
        :error="errores.telefono"
      />
    </div>

    <CampoDocumento
      v-model:tipo="tipoDocumento"
      v-model:numero="datos.numero_documento"
      :tipo-bloqueado="cuenta.tipo_documento === 'ce'"
      :error="errorNumero"
      :ayuda="cuenta.tipo_documento === 'ce' ? 'Tu documento no se cambia desde aquí.' : undefined"
    >
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
      >
        <BaseAviso
          v-if="cambiaTipo"
          tono="aviso"
          titulo="Cambiarás tu DNI por un carné de extranjería"
          class="mb-4"
        >
          Al guardar te pediremos tu contraseña y una última confirmación. Si no es lo que querías,
          vuelve a elegir DNI.
        </BaseAviso>
      </Transition>
    </CampoDocumento>

    <BaseCampo
      v-if="esGerente"
      v-model="datos.nombre_recibos"
      etiqueta="Nombre como figura en tus recibos"
      ayuda="Escríbelo tal como aparece en tus recibos de luz, agua u otros servicios."
      capitalizar
      :maximo="120"
      :error="errores.nombre_recibos"
    />
    <BaseCampo
      :model-value="cuenta.cargo ?? 'Sin cargo asignado'"
      etiqueta="Cargo"
      solo-lectura
      :ayuda="ayudaCargo"
    />

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div v-if="pideContrasena" class="rounded-[10px] border border-borde bg-fondo p-4 pb-0">
        <BaseCampo
          v-model="contrasena"
          etiqueta="Contraseña actual"
          tipo="password"
          autocompletar="current-password"
          ayuda="Cambiar tu correo o tu documento requiere tu contraseña."
          :error="errores.contrasena_actual"
        />
      </div>
    </Transition>

    <BaseAviso v-if="guardado" tono="exito" class="mt-5">
      Tus datos se guardaron. Ya se ven en toda tu cuenta.
    </BaseAviso>

    <div
      class="mt-6 flex flex-col gap-3 border-t border-borde pt-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <p class="text-[12px] text-secundario" aria-live="polite">
        {{ resumen }}
        <span class="block">Tus datos personales se guardan cifrados.</span>
      </p>
      <div class="flex flex-col-reverse gap-2 sm:flex-row">
        <BaseBoton
          v-if="hayCambios"
          variante="secundario"
          :deshabilitado="enviando"
          @click="descartar"
        >
          Descartar cambios
        </BaseBoton>
        <BaseBoton tipo="submit" :cargando="enviando" :deshabilitado="!puedeGuardar">
          {{ enviando ? 'Guardando…' : 'Guardar mis datos' }}
        </BaseBoton>
      </div>
    </div>

    <DialogoCambioDocumento
      :modo="dialogoDocumento"
      :dni-actual="cuenta.numero_documento"
      :carne-nuevo="actuales.numero_documento.replace(/[\s-]/g, '').toUpperCase()"
      @confirmar="confirmarDocumento"
      @cancelar="dialogoDocumento = null"
    />
    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos guardar tus datos"
      :etiquetas="ETIQUETAS"
      @cerrar="cerrarFallo"
      @reintentar="enviar"
    />
  </form>
</template>
