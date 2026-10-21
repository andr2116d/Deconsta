<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import type { AccionAsistente, Asistente } from '../types'

/**
 * Confirma una acción sobre una asistente (bloquear, eliminar o restablecer su contraseña), con un
 * motivo opcional que queda en el historial.
 */
const props = defineProps<{
  accion: { tipo: AccionAsistente; asistente: Asistente } | null
  enviando: boolean
}>()
const emit = defineEmits<{ confirmar: [motivo: string | null]; cancelar: [] }>()

const TEXTOS: Record<
  AccionAsistente,
  { titulo: string; icono: NombreIcono; puntos: string[]; confirmar: string }
> = {
  bloquear: {
    titulo: '¿Bloquear a {nombre}?',
    icono: 'candado',
    puntos: [
      'Se cerrarán sus sesiones abiertas.',
      'No podrá ingresar hasta que la desbloquees desde Mi equipo.',
    ],
    confirmar: 'Bloquear cuenta',
  },
  eliminar: {
    titulo: '¿Eliminar a {nombre}?',
    icono: 'alerta',
    puntos: [
      'No podrá ingresar y sus sesiones abiertas se cerrarán.',
      'Su historial se conserva: si vuelve, podrás recuperar su cuenta.',
      'Lo que tenga pendiente seguirá disponible para las demás asistentes de tu equipo.',
    ],
    confirmar: 'Eliminar cuenta',
  },
  restablecer: {
    titulo: '¿Restablecer la contraseña de {nombre}?',
    icono: 'candado',
    puntos: [
      'Deconsta generará una contraseña temporal nueva que verás una sola vez para entregársela.',
      'Su contraseña actual dejará de servir y se cerrarán sus sesiones abiertas.',
      'Al ingresar se le pedirá cambiarla por una que solo ella conozca.',
    ],
    confirmar: 'Restablecer contraseña',
  },
}

const motivo = ref('')
const idMotivo = useId()
watch(
  () => props.accion,
  () => (motivo.value = ''),
)

const textos = computed(() => (props.accion ? TEXTOS[props.accion.tipo] : null))
const titulo = computed(() => {
  if (!props.accion || !textos.value) return ''
  const { nombres, apellidos } = props.accion.asistente
  return textos.value.titulo.replace('{nombre}', `${nombres} ${apellidos}`)
})
const destructiva = computed(() => props.accion?.tipo === 'eliminar')

function confirmar() {
  emit('confirmar', motivo.value.trim() || null)
}
</script>

<template>
  <BaseDialogo :abierto="accion !== null" :titulo="titulo" @cerrar="emit('cancelar')">
    <template #icono>
      <BaseIcono :nombre="textos?.icono ?? 'alerta'" class="size-5" />
    </template>
    <template v-if="textos">
      <ul class="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[13px] text-secundario">
        <li v-for="punto in textos.puntos" :key="punto">{{ punto }}</li>
      </ul>
      <div class="mt-5 flex flex-col gap-1.5">
        <label :for="idMotivo" class="text-[12px] font-bold">Motivo (opcional)</label>
        <textarea
          :id="idMotivo"
          v-model="motivo"
          rows="2"
          maxlength="500"
          class="w-full resize-none rounded-[7px] border border-control px-3 py-2.5 text-[14px] transition-colors duration-200 hover:border-tinta"
        />
        <p class="text-[12px] text-secundario">Quedará en el historial de la cuenta.</p>
      </div>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" :deshabilitado="enviando" @click="emit('cancelar')">
          Cancelar
        </BaseBoton>
        <button
          v-if="destructiva"
          type="button"
          class="inline-flex min-h-11 items-center justify-center gap-2 rounded-[9px] border border-error bg-error px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-[#8a2f34] disabled:opacity-70"
          :disabled="enviando"
          :aria-busy="enviando"
          @click="confirmar"
        >
          <span
            v-if="enviando"
            aria-hidden="true"
            class="size-4 animate-girar rounded-full border-2 border-current border-t-transparent"
          />
          {{ textos.confirmar }}
        </button>
        <BaseBoton v-else :cargando="enviando" @click="confirmar">{{ textos.confirmar }}</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
