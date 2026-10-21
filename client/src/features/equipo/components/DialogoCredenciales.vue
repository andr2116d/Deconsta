<script setup lang="ts">
import { computed } from 'vue'

import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import { useCopiar } from '@/shared/composables/useCopiar'

import type { Credenciales } from '../types'

/**
 * Entrega el usuario y la contraseña temporal de una asistente nueva o recuperada. Es la única vez
 * que se muestran: Deconsta solo guarda el hash de la contraseña.
 */
const props = defineProps<{ credenciales: Credenciales | null; recuperada?: boolean }>()
const emit = defineEmits<{ cerrar: [] }>()

const { copiado, fallo, copiar } = useCopiar()

const nombre = computed(() =>
  props.credenciales
    ? `${props.credenciales.asistente.nombres} ${props.credenciales.asistente.apellidos}`
    : '',
)
const ambos = computed(() =>
  props.credenciales
    ? `Usuario: ${props.credenciales.nombre_usuario}\nContraseña temporal: ${props.credenciales.contrasena_temporal}`
    : '',
)
</script>

<template>
  <BaseDialogo
    :abierto="credenciales !== null"
    :titulo="recuperada ? 'Cuenta recuperada.' : 'Cuenta creada.'"
    @cerrar="emit('cerrar')"
  >
    <template #icono>
      <BaseIcono nombre="check" class="size-5" />
    </template>
    <template v-if="credenciales">
      <p class="mt-2 text-[13px] text-secundario">
        Entrega a <strong class="text-tinta">{{ nombre }}</strong> estos datos para su primer
        ingreso. Al entrar aceptará las políticas, se le pedirá cambiar la contraseña y confirmará
        sus datos.
      </p>

      <dl class="mt-5 flex flex-col gap-3">
        <div
          v-for="dato in [
            { clave: 'usuario', etiqueta: 'Usuario', valor: credenciales.nombre_usuario },
            {
              clave: 'contrasena',
              etiqueta: 'Contraseña temporal',
              valor: credenciales.contrasena_temporal,
            },
          ]"
          :key="dato.clave"
          class="flex items-center gap-3 rounded-[10px] border border-borde bg-fondo p-3"
        >
          <div class="min-w-0 flex-1">
            <dt class="text-[11px] text-secundario">{{ dato.etiqueta }}</dt>
            <dd class="font-mono text-[15px] font-bold break-all text-tinta">{{ dato.valor }}</dd>
          </div>
          <BaseBoton variante="secundario" @click="copiar(dato.valor, dato.clave)">
            <BaseIcono :nombre="copiado === dato.clave ? 'check' : 'documento'" class="size-4" />
            {{ copiado === dato.clave ? 'Copiado' : 'Copiar' }}
            <span class="sr-only">{{ dato.etiqueta.toLowerCase() }}</span>
          </BaseBoton>
        </div>
      </dl>

      <p class="sr-only" aria-live="polite">
        {{ copiado ? 'Copiado al portapapeles.' : '' }}
      </p>
      <BaseAviso v-if="fallo" tono="aviso" class="mt-4">
        Tu navegador no permitió copiar. Selecciona el texto y cópialo a mano.
      </BaseAviso>
      <BaseAviso tono="info" class="mt-4">
        Esta contraseña se muestra solo ahora. Compártela por un canal seguro.
      </BaseAviso>

      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" @click="copiar(ambos, 'ambos')">
          {{ copiado === 'ambos' ? 'Copiados' : 'Copiar usuario y contraseña' }}
        </BaseBoton>
        <BaseBoton @click="emit('cerrar')">Listo</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
