<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'

import MedidorSeguridad from '@/features/acceso/components/MedidorSeguridad.vue'
import { useSeguridadContrasena } from '@/features/acceso/composables/useSeguridadContrasena'
import { ErrorApi } from '@/shared/api/http'
import { useLimpiarErrores } from '@/shared/composables/useLimpiarErrores'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'
import CampoDocumento from '@/shared/components/CampoDocumento.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'
import {
  avisoCelular,
  celularValido,
  documentoValido,
  filtrarCelular,
  filtrarNombre,
  type TipoDocumento,
} from '@/shared/validaciones/persona'

import { avisoUsuario, filtrarUsuario, sugerirUsuario, usuarioValido } from '../credenciales'
import { useEquipoStore } from '../stores/equipo'
import type { Credenciales, CuentaEliminada, NuevaAsistente } from '../types'
import DialogoAsistenteEliminada from './DialogoAsistenteEliminada.vue'

const emit = defineEmits<{
  creada: [credenciales: Credenciales, recuperada: boolean]
  'sesion-terminada': []
}>()

type Campo =
  | 'nombres'
  | 'apellidos'
  | 'telefono'
  | 'numero_documento'
  | 'cargo'
  | 'nombre_usuario'
  | 'contrasena'

const ETIQUETAS: Record<Campo, string> = {
  nombres: 'Nombres',
  apellidos: 'Apellidos',
  telefono: 'Celular',
  numero_documento: 'Documento',
  cargo: 'Cargo',
  nombre_usuario: 'Usuario',
  contrasena: 'Contraseña inicial',
}

const store = useEquipoStore()
const formulario = ref<HTMLFormElement>()
const datos = reactive({
  nombres: '',
  apellidos: '',
  telefono: '',
  tipo_documento: 'dni' as TipoDocumento,
  numero_documento: '',
  cargo: '',
  nombre_usuario: '',
  contrasena: '',
})
const modos = reactive({ usuario: 'generado', contrasena: 'generada' } as {
  usuario: 'generado' | 'elegido'
  contrasena: 'generada' | 'elegida'
})
const errores = reactive<Partial<Record<Campo, string>>>({})
const enviando = ref(false)
useLimpiarErrores(datos, errores)
const fallo = ref<ErrorApi | null>(null)
const eliminada = ref<CuentaEliminada | null>(null)

const sugerido = computed(() => sugerirUsuario(datos.nombres, datos.apellidos))
const usuarioFinal = computed(() =>
  modos.usuario === 'elegido' ? datos.nombre_usuario : sugerido.value,
)
const { requisitos, puntaje, nivel } = useSeguridadContrasena(
  () => datos.contrasena,
  () => usuarioFinal.value,
)

function limpiarErrores() {
  for (const campo of Object.keys(errores) as Campo[]) delete errores[campo]
}

async function enfocarPrimerError() {
  await nextTick()
  formulario.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

/** Mensajes claros y específicos antes de enviar; el backend vuelve a validar todo. */
function validar(): boolean {
  limpiarErrores()
  if (!datos.nombres.trim()) errores.nombres = 'Escribe sus nombres.'
  if (!datos.apellidos.trim()) errores.apellidos = 'Escribe sus apellidos.'
  if (!datos.telefono) errores.telefono = 'Escribe su número de celular.'
  else if (!celularValido(datos.telefono)) {
    errores.telefono = 'Escribe un celular de 9 dígitos que empiece con 9.'
  }
  if (!datos.numero_documento) errores.numero_documento = 'Escribe su número de documento.'
  else if (!documentoValido(datos.tipo_documento, datos.numero_documento)) {
    errores.numero_documento =
      datos.tipo_documento === 'dni'
        ? 'El DNI debe tener 8 dígitos.'
        : 'El carné debe tener de 9 a 12 letras o dígitos.'
  }
  if (modos.usuario === 'elegido' && !usuarioValido(datos.nombre_usuario)) {
    errores.nombre_usuario =
      "Usa de 3 a 40 letras minúsculas, números, '.', '_' o '-', empezando y terminando en letra o número."
  }
  if (modos.contrasena === 'elegida' && !datos.contrasena) {
    errores.contrasena = 'Escribe la contraseña inicial o deja que Deconsta la genere.'
  }
  return Object.keys(errores).length === 0
}

function solicitud(crearAunqueEliminada = false): NuevaAsistente {
  return {
    nombres: datos.nombres,
    apellidos: datos.apellidos,
    telefono: datos.telefono,
    tipo_documento: datos.tipo_documento,
    numero_documento: datos.numero_documento,
    cargo: datos.cargo.trim() || null,
    nombre_usuario: modos.usuario === 'elegido' ? datos.nombre_usuario : null,
    contrasena: modos.contrasena === 'elegida' ? datos.contrasena : null,
    crear_aunque_eliminada: crearAunqueEliminada,
  }
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
  if (comoApi.codigo === 'ASISTENTE_ELIMINADA') {
    eliminada.value = comoApi.cuerpo.deleted_account as CuentaEliminada
    return
  }
  Object.assign(errores, comoApi.campos)
  fallo.value = comoApi
}

async function enviar(crearAunqueEliminada = false) {
  if (enviando.value) return
  if (!validar()) {
    enfocarPrimerError()
    return
  }
  fallo.value = null
  enviando.value = true
  try {
    const credenciales = await store.registrar(solicitud(crearAunqueEliminada))
    eliminada.value = null
    emit('creada', credenciales, false)
  } catch (error) {
    eliminada.value = null
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}

async function recuperar() {
  if (!eliminada.value || enviando.value) return
  enviando.value = true
  try {
    const credenciales = await store.recuperar(eliminada.value.id)
    eliminada.value = null
    emit('creada', credenciales, true)
  } catch (error) {
    eliminada.value = null
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}

function cerrarFallo() {
  fallo.value = null
  enfocarPrimerError()
}
</script>

<template>
  <form ref="formulario" novalidate :aria-busy="enviando" @submit.prevent="enviar()">
    <h2 class="text-[19px] leading-tight font-extrabold tracking-[-0.02em]">
      Datos de la asistente
    </h2>
    <p class="mt-1.5 mb-6 text-[13px] text-secundario">
      Su correo lo completará ella al ingresar por primera vez.
    </p>

    <div class="grid gap-x-5 sm:grid-cols-2">
      <BaseCampo
        v-model="datos.nombres"
        etiqueta="Nombres"
        autocompletar="off"
        capitalizar
        :maximo="80"
        :filtro="filtrarNombre"
        :error="errores.nombres"
      />
      <BaseCampo
        v-model="datos.apellidos"
        etiqueta="Apellidos"
        autocompletar="off"
        capitalizar
        :maximo="80"
        :filtro="filtrarNombre"
        :error="errores.apellidos"
      />
      <BaseCampo
        v-model="datos.telefono"
        etiqueta="Celular"
        tipo="tel"
        autocompletar="off"
        modo-entrada="numeric"
        prefijo="+51"
        :filtro="filtrarCelular"
        :aviso="avisoCelular(datos.telefono)"
        :error="errores.telefono"
      />
      <BaseCampo
        v-model="datos.cargo"
        etiqueta="Cargo (opcional)"
        autocompletar="off"
        capitalizar
        :maximo="80"
        ayuda="Por ejemplo, Asistente administrativa. Ella no podrá cambiarlo."
        :error="errores.cargo"
      />
    </div>
    <CampoDocumento
      v-model:tipo="datos.tipo_documento"
      v-model:numero="datos.numero_documento"
      :error="errores.numero_documento"
    />

    <fieldset class="mt-2 border-t border-borde pt-5">
      <legend class="text-[15px] font-extrabold">Usuario de acceso</legend>
      <div class="mt-3 mb-4 flex flex-wrap gap-2">
        <label
          v-for="opcion in [
            { valor: 'generado', texto: 'Que Deconsta lo genere' },
            { valor: 'elegido', texto: 'Elegir un usuario' },
          ]"
          :key="opcion.valor"
          class="flex min-h-11 cursor-pointer items-center gap-2 rounded-[9px] border px-3 text-[13px] transition-colors duration-200"
          :class="
            modos.usuario === opcion.valor
              ? 'border-acento bg-acento-suave font-bold text-acento'
              : 'border-borde hover:border-control'
          "
        >
          <input
            v-model="modos.usuario"
            type="radio"
            name="modo-usuario"
            :value="opcion.valor"
            class="accent-[var(--color-acento)]"
          />
          {{ opcion.texto }}
        </label>
      </div>
      <BaseCampo
        v-if="modos.usuario === 'elegido'"
        v-model="datos.nombre_usuario"
        etiqueta="Usuario"
        autocompletar="off"
        prefijo="@"
        :filtro="filtrarUsuario"
        :aviso="avisoUsuario(datos.nombre_usuario)"
        :error="errores.nombre_usuario"
        ayuda="Letras minúsculas, números, punto, guion o guion bajo."
      />
      <p v-else class="mb-4 rounded-[10px] bg-fondo p-3 text-[13px] text-secundario">
        <template v-if="sugerido">
          Será <strong class="text-tinta">@{{ sugerido }}</strong
          >; si ya existe, se le agregará un número.
        </template>
        <template v-else>Se generará a partir de su primer nombre y su primer apellido.</template>
      </p>
    </fieldset>

    <fieldset class="border-t border-borde pt-5">
      <legend class="text-[15px] font-extrabold">Contraseña inicial</legend>
      <div class="mt-3 mb-4 flex flex-wrap gap-2">
        <label
          v-for="opcion in [
            { valor: 'generada', texto: 'Generar una contraseña segura' },
            { valor: 'elegida', texto: 'Definir la contraseña' },
          ]"
          :key="opcion.valor"
          class="flex min-h-11 cursor-pointer items-center gap-2 rounded-[9px] border px-3 text-[13px] transition-colors duration-200"
          :class="
            modos.contrasena === opcion.valor
              ? 'border-acento bg-acento-suave font-bold text-acento'
              : 'border-borde hover:border-control'
          "
        >
          <input
            v-model="modos.contrasena"
            type="radio"
            name="modo-contrasena"
            :value="opcion.valor"
            class="accent-[var(--color-acento)]"
          />
          {{ opcion.texto }}
        </label>
      </div>
      <BaseCampo
        v-if="modos.contrasena === 'elegida'"
        v-model="datos.contrasena"
        etiqueta="Contraseña inicial"
        tipo="password"
        autocompletar="new-password"
        :error="errores.contrasena"
      >
        <MedidorSeguridad
          :puntaje="puntaje"
          :nivel="nivel"
          :requisitos="requisitos"
          :visible="datos.contrasena.length > 0"
        />
      </BaseCampo>
      <p v-else class="mb-4 rounded-[10px] bg-fondo p-3 text-[13px] text-secundario">
        Deconsta creará una contraseña de 14 caracteres. La verás una sola vez al crear la cuenta.
      </p>
      <p class="text-[12px] text-secundario">
        En ambos casos es temporal: se le pedirá cambiarla en cada ingreso hasta que lo haga.
      </p>
    </fieldset>

    <div
      class="mt-6 flex flex-col-reverse gap-2 border-t border-borde pt-5 sm:flex-row sm:justify-end"
    >
      <slot name="cancelar" />
      <BaseBoton tipo="submit" :cargando="enviando">
        {{ enviando ? 'Creando la cuenta…' : 'Crear cuenta de asistente' }}
      </BaseBoton>
    </div>

    <DialogoAsistenteEliminada
      :cuenta="eliminada"
      :nombre="`${datos.nombres} ${datos.apellidos}`"
      :enviando="enviando"
      @recuperar="recuperar"
      @crear-nueva="enviar(true)"
      @cancelar="eliminada = null"
    />
    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos crear la cuenta"
      :etiquetas="ETIQUETAS"
      @cerrar="cerrarFallo"
      @reintentar="enviar()"
    />
  </form>
</template>
