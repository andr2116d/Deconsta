<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'

import { useSesionStore } from '../stores/sesion'
import type { Ingreso } from '../types'

const emit = defineEmits<{ ingreso: [ingreso: Ingreso] }>()

interface Aviso {
  tono: 'error' | 'aviso'
  titulo: string
  mensaje: string
}

const sesion = useSesionStore()
const datos = reactive({ nombre_usuario: '', contrasena: '' })
const errores = reactive<{ nombre_usuario?: string; contrasena?: string }>({})
const aviso = ref<Aviso | null>(null)
const enviando = ref(false)
const campoUsuario = ref<InstanceType<typeof BaseCampo>>()
const campoContrasena = ref<InstanceType<typeof BaseCampo>>()

// Tras un 429, el botón espera lo que indica Retry-After. Es solo una ayuda: el servidor decide.
const esperaHasta = ref(0)
const ahora = ref(Date.now())
let reloj: ReturnType<typeof setInterval> | undefined
const segundosEspera = computed(() =>
  Math.max(0, Math.ceil((esperaHasta.value - ahora.value) / 1000)),
)

function iniciarEspera(segundos: number) {
  esperaHasta.value = Date.now() + segundos * 1000
  ahora.value = Date.now()
  clearInterval(reloj)
  reloj = setInterval(() => {
    ahora.value = Date.now()
    if (segundosEspera.value === 0) clearInterval(reloj)
  }, 1000)
}
onBeforeUnmount(() => clearInterval(reloj))

const textoBoton = computed(() => {
  if (enviando.value) return 'Ingresando…'
  if (segundosEspera.value > 0) {
    const m = Math.floor(segundosEspera.value / 60)
    const s = String(segundosEspera.value % 60).padStart(2, '0')
    return `Espera ${m}:${s}`
  }
  return 'Iniciar sesión'
})

function validar(): boolean {
  errores.nombre_usuario = datos.nombre_usuario.trim() ? undefined : 'Ingresa tu nombre de usuario.'
  errores.contrasena = datos.contrasena ? undefined : 'Ingresa tu contraseña.'
  if (errores.nombre_usuario) campoUsuario.value?.enfocar()
  else if (errores.contrasena) campoContrasena.value?.enfocar()
  return !errores.nombre_usuario && !errores.contrasena
}

function mostrarError(error: unknown) {
  if (!(error instanceof ErrorApi)) {
    aviso.value = {
      tono: 'error',
      titulo: 'No pudimos iniciar sesión',
      mensaje: 'Ocurrió un error inesperado. Inténtalo de nuevo.',
    }
    return
  }
  switch (error.codigo) {
    case 'CAMPOS_OBLIGATORIOS':
    case 'DATOS_INVALIDOS':
      Object.assign(errores, error.campos)
      break
    case 'CREDENCIALES_INCORRECTAS':
      aviso.value = { tono: 'error', titulo: 'Datos incorrectos', mensaje: error.message }
      datos.contrasena = ''
      campoContrasena.value?.enfocar()
      break
    case 'CUENTA_BLOQUEADA':
      aviso.value = { tono: 'aviso', titulo: 'Cuenta bloqueada', mensaje: error.message }
      datos.contrasena = ''
      break
    case 'DEMASIADAS_SOLICITUDES':
      iniciarEspera(error.reintentarEn ?? 60)
      aviso.value = { tono: 'aviso', titulo: 'Demasiados intentos', mensaje: error.message }
      break
    default:
      aviso.value = {
        tono: 'error',
        titulo: 'No pudimos iniciar sesión',
        mensaje: error.referencia
          ? `${error.message} Referencia: ${error.referencia}`
          : error.message,
      }
  }
}

async function enviar() {
  // Un segundo envío mientras el primero sigue en curso se ignora.
  if (enviando.value || segundosEspera.value > 0) return
  aviso.value = null
  if (!validar()) return
  enviando.value = true
  try {
    emit('ingreso', await sesion.ingresar({ ...datos }))
  } catch (error) {
    mostrarError(error)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <form novalidate :aria-busy="enviando" @submit.prevent="enviar">
    <BaseCampo
      ref="campoUsuario"
      v-model="datos.nombre_usuario"
      etiqueta="Usuario"
      autocompletar="username"
      :error="errores.nombre_usuario"
    />
    <BaseCampo
      ref="campoContrasena"
      v-model="datos.contrasena"
      etiqueta="Contraseña"
      tipo="password"
      autocompletar="current-password"
      :error="errores.contrasena"
    />

    <BaseAviso v-if="aviso" :tono="aviso.tono" :titulo="aviso.titulo" class="mb-1">
      {{ aviso.mensaje }}
    </BaseAviso>

    <BaseBoton
      tipo="submit"
      ancho="completo"
      class="mt-4"
      :cargando="enviando"
      :deshabilitado="segundosEspera > 0"
    >
      {{ textoBoton }}
      <svg
        v-if="!enviando && segundosEspera === 0"
        aria-hidden="true"
        viewBox="0 0 24 24"
        class="size-4 fill-none stroke-current stroke-2"
      >
        <path d="M5 12h14m-5-5 5 5-5 5" />
      </svg>
    </BaseBoton>
  </form>
</template>
