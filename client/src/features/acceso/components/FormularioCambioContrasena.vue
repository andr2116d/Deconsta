<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseCampo from '@/shared/components/BaseCampo.vue'

import { useSeguridadContrasena } from '../composables/useSeguridadContrasena'
import { useSesionStore } from '../stores/sesion'
import MedidorSeguridad from './MedidorSeguridad.vue'

defineProps<{ inicial: boolean }>()
const emit = defineEmits<{ cambiada: []; omitir: []; 'sesion-terminada': [] }>()

type Campo = 'contrasena_actual' | 'contrasena_nueva' | 'confirmacion'

const sesion = useSesionStore()
const datos = reactive({ contrasena_actual: '', contrasena_nueva: '', confirmacion: '' })
const errores = reactive<Partial<Record<Campo, string>>>({})
const aviso = ref<string | null>(null)
const enviando = ref(false)

const { requisitos, puntaje, nivel } = useSeguridadContrasena(
  () => datos.contrasena_nueva,
  () => sesion.usuario?.nombre_usuario ?? '',
)
const escribiendo = computed(() => datos.contrasena_nueva.length > 0)

function validar(): boolean {
  errores.contrasena_actual = datos.contrasena_actual ? undefined : 'Ingresa tu contraseña actual.'
  errores.contrasena_nueva = datos.contrasena_nueva ? undefined : 'Ingresa la nueva contraseña.'
  errores.confirmacion =
    datos.confirmacion === datos.contrasena_nueva ? undefined : 'Las contraseñas no coinciden.'
  return !Object.values(errores).some(Boolean)
}

function mostrarError(error: unknown) {
  if (!(error instanceof ErrorApi)) {
    aviso.value = 'Ocurrió un error inesperado. Inténtalo de nuevo.'
    return
  }
  if (error.codigo === 'NO_AUTENTICADO') {
    emit('sesion-terminada')
    return
  }
  const campos = error.campos as Partial<Record<Campo, string>>
  if (campos.contrasena_actual || campos.contrasena_nueva) {
    Object.assign(errores, campos)
    if (error.codigo === 'CONTRASENA_ACTUAL_INCORRECTA') datos.contrasena_actual = ''
    return
  }
  aviso.value = error.referencia
    ? `${error.message} Referencia: ${error.referencia}`
    : error.message
}

async function enviar() {
  if (enviando.value) return
  aviso.value = null
  if (!validar()) return
  enviando.value = true
  try {
    await sesion.cambiarContrasena({
      contrasena_actual: datos.contrasena_actual,
      contrasena_nueva: datos.contrasena_nueva,
    })
    emit('cambiada')
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
      v-model="datos.contrasena_actual"
      :etiqueta="inicial ? 'Contraseña temporal' : 'Contraseña actual'"
      tipo="password"
      autocompletar="current-password"
      :error="errores.contrasena_actual"
    />
    <BaseCampo
      v-model="datos.contrasena_nueva"
      etiqueta="Nueva contraseña"
      tipo="password"
      autocompletar="new-password"
      :error="errores.contrasena_nueva"
    >
      <MedidorSeguridad
        :puntaje="puntaje"
        :nivel="nivel"
        :requisitos="requisitos"
        :visible="escribiendo"
      />
    </BaseCampo>
    <BaseCampo
      v-model="datos.confirmacion"
      etiqueta="Repite la nueva contraseña"
      tipo="password"
      autocompletar="new-password"
      :error="errores.confirmacion"
    />

    <BaseAviso v-if="aviso" tono="error" titulo="No pudimos guardar la contraseña" class="mb-1">
      {{ aviso }}
    </BaseAviso>

    <div class="mt-4 flex flex-col gap-2">
      <BaseBoton tipo="submit" ancho="completo" :cargando="enviando">
        {{ enviando ? 'Guardando…' : 'Guardar contraseña' }}
      </BaseBoton>
      <BaseBoton
        variante="discreto"
        ancho="completo"
        :deshabilitado="enviando"
        @click="emit('omitir')"
      >
        {{ inicial ? 'Omitir por ahora' : 'Volver' }}
      </BaseBoton>
    </div>
  </form>
</template>
