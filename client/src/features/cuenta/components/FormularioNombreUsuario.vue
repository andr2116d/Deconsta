<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'

import { formatearDiaYMes, NOMBRE_USUARIO_VALIDO, normalizarNombreUsuario } from '../datos'
import { useCuentaStore } from '../stores/cuenta'
import type { Cuenta } from '../types'
import DialogoFalloGuardado from './DialogoFalloGuardado.vue'

const props = defineProps<{ cuenta: Cuenta }>()
const emit = defineEmits<{ 'sesion-terminada': [] }>()

const REGLA =
  "Usa de 3 a 40 letras minúsculas, números, '.', '_' o '-', empezando y terminando en letra o número."
const ETIQUETAS = { nombre_usuario: 'Nuevo usuario', contrasena_actual: 'Contraseña actual' }

const store = useCuentaStore()
const formulario = ref<HTMLFormElement>()
const nuevo = ref(props.cuenta.nombre_usuario)
const contrasena = ref('')
const errores = ref<Record<string, string>>({})
const enviando = ref(false)
const cambiado = ref<string | null>(null)
const fallo = ref<ErrorApi | null>(null)

const cupo = computed(() => props.cuenta.cambios_nombre_usuario)
const sinCupo = computed(() => cupo.value.restantes === 0)
const renovacion = computed(() => formatearDiaYMes(cupo.value.renueva_en))
const normalizado = computed(() => normalizarNombreUsuario(nuevo.value))
const hayCambio = computed(
  () => normalizado.value.length > 0 && normalizado.value !== props.cuenta.nombre_usuario,
)
const formatoValido = computed(() => NOMBRE_USUARIO_VALIDO.test(normalizado.value))
const puedeGuardar = computed(() => hayCambio.value && formatoValido.value && !sinCupo.value)
const errorUsuario = computed(() =>
  hayCambio.value && !formatoValido.value ? REGLA : errores.value.nombre_usuario,
)
// El usuario se guarda en minúsculas: se muestra cómo quedará si se escribió distinto.
const vistaPrevia = computed(() =>
  hayCambio.value && formatoValido.value && normalizado.value !== nuevo.value
    ? `Quedará como @${normalizado.value}.`
    : undefined,
)

watch(
  () => props.cuenta.nombre_usuario,
  (actual) => {
    nuevo.value = actual
    contrasena.value = ''
  },
)
watch(hayCambio, (hay) => {
  if (hay) cambiado.value = null
})

function mostrarFallo(error: unknown) {
  const comoApi =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
  if (comoApi.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return
  }
  errores.value = { ...comoApi.campos }
  if (comoApi.codigo === 'CONTRASENA_ACTUAL_INCORRECTA') contrasena.value = ''
  fallo.value = comoApi
}

async function cerrarFallo() {
  fallo.value = null
  await nextTick()
  formulario.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

async function guardar() {
  if (!puedeGuardar.value || enviando.value) return
  errores.value = {}
  if (!contrasena.value) {
    errores.value = { contrasena_actual: 'Confirma el cambio con tu contraseña actual.' }
    await nextTick()
    formulario.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
    return
  }
  await enviar()
}

async function enviar() {
  fallo.value = null
  enviando.value = true
  try {
    const cuenta = await store.cambiarNombreUsuario({
      nombre_usuario: normalizado.value,
      contrasena_actual: contrasena.value,
    })
    cambiado.value = cuenta.nombre_usuario
  } catch (error) {
    mostrarFallo(error)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <form ref="formulario" novalidate :aria-busy="enviando" @submit.prevent="guardar">
    <div
      class="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[10px] bg-fondo p-4 text-[13px]"
    >
      <div
        role="meter"
        aria-label="Cambios de usuario disponibles este mes"
        aria-valuemin="0"
        :aria-valuemax="cupo.maximo"
        :aria-valuenow="cupo.restantes"
        :aria-valuetext="`${cupo.restantes} de ${cupo.maximo}`"
        class="flex gap-1"
      >
        <span
          v-for="n in cupo.maximo"
          :key="n"
          class="h-2 w-6 rounded-full transition-colors duration-300"
          :class="n <= cupo.restantes ? 'bg-acento' : 'bg-borde'"
        />
      </div>
      <p>
        <strong>
          {{
            sinCupo
              ? 'Ya usaste tus cambios de este mes.'
              : `Te ${cupo.restantes === 1 ? 'queda 1 cambio' : `quedan ${cupo.restantes} cambios`} de usuario este mes.`
          }}
        </strong>
        <span class="block text-secundario">
          Puedes cambiarlo hasta {{ cupo.maximo }} veces al mes. Se renuevan el {{ renovacion }}.
        </span>
      </p>
    </div>

    <BaseCampo
      v-model="nuevo"
      etiqueta="Usuario de acceso"
      autocompletar="username"
      :maximo="64"
      :deshabilitado="sinCupo"
      :error="errorUsuario"
      :ayuda="vistaPrevia ?? 'Es el nombre con el que ingresas a Deconsta.'"
    />

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
    >
      <BaseCampo
        v-if="hayCambio && formatoValido && !sinCupo"
        v-model="contrasena"
        etiqueta="Contraseña actual"
        tipo="password"
        autocompletar="current-password"
        ayuda="Por seguridad, confirma el cambio con tu contraseña."
        :error="errores.contrasena_actual"
      />
    </Transition>

    <BaseAviso v-if="cambiado" tono="exito" class="mb-4">
      Tu usuario ahora es @{{ cambiado }}. Úsalo en tu próximo ingreso.
    </BaseAviso>

    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-[12px] text-secundario">
        {{
          puedeGuardar
            ? `Después te ${cupo.restantes - 1 === 1 ? 'quedará 1 cambio' : `quedarán ${cupo.restantes - 1} cambios`} este mes.`
            : 'Tu sesión actual sigue abierta al cambiarlo.'
        }}
      </p>
      <BaseBoton tipo="submit" :cargando="enviando" :deshabilitado="!puedeGuardar">
        {{ enviando ? 'Guardando…' : 'Cambiar usuario' }}
      </BaseBoton>
    </div>

    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos cambiar tu usuario"
      :etiquetas="ETIQUETAS"
      @cerrar="cerrarFallo"
      @reintentar="enviar"
    />
  </form>
</template>
