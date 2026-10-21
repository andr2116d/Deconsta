<script setup lang="ts">
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { CuentaEliminada } from '../types'

/** La persona ya estuvo en el equipo y se eliminó: recuperar su cuenta o empezar de cero. */
defineProps<{ cuenta: CuentaEliminada | null; nombre: string; enviando: boolean }>()
const emit = defineEmits<{ recuperar: []; crearNueva: []; cancelar: [] }>()
</script>

<template>
  <BaseDialogo
    :abierto="cuenta !== null"
    titulo="Ya registraste a esta persona antes."
    @cerrar="emit('cancelar')"
  >
    <template #icono>
      <BaseIcono nombre="equipo" class="size-5" />
    </template>
    <template v-if="cuenta">
      <p class="mt-2 text-[13px] text-secundario">
        Eliminaste la cuenta de <strong class="text-tinta">{{ nombre }}</strong> (@{{
          cuenta.nombre_usuario
        }}). ¿Volvió a tu equipo?
      </p>
      <div class="mt-5 flex flex-col gap-3">
        <button
          type="button"
          class="flex items-start gap-3 rounded-[10px] border border-borde p-4 text-left transition-colors duration-200 hover:border-acento hover:bg-acento-suave disabled:opacity-70"
          :disabled="enviando"
          @click="emit('recuperar')"
        >
          <BaseIcono nombre="reloj" class="mt-0.5 size-5 text-acento" />
          <span>
            <strong class="block text-[14px]">Recuperar su cuenta</strong>
            <span class="text-[12px] text-secundario">
              Conserva su usuario y su historial. Recibirá una contraseña temporal nueva.
            </span>
          </span>
        </button>
        <button
          type="button"
          class="flex items-start gap-3 rounded-[10px] border border-borde p-4 text-left transition-colors duration-200 hover:border-acento hover:bg-acento-suave disabled:opacity-70"
          :disabled="enviando"
          @click="emit('crearNueva')"
        >
          <BaseIcono nombre="mas" class="mt-0.5 size-5 text-acento" />
          <span>
            <strong class="block text-[14px]">Crear una cuenta nueva desde cero</strong>
            <span class="text-[12px] text-secundario">
              Con los datos que acabas de escribir. La cuenta anterior sigue eliminada.
            </span>
          </span>
        </button>
      </div>
      <div class="mt-5 flex justify-end">
        <BaseBoton variante="discreto" :deshabilitado="enviando" @click="emit('cancelar')">
          Cancelar
        </BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
