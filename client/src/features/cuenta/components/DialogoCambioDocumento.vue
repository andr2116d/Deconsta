<script setup lang="ts">
import { ref, watch } from 'vue'

import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseDialogo from '@/shared/components/BaseDialogo.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

/**
 * Advertencias seguidas para pasar de DNI a carné de extranjería, un caso excepcional:
 * - «inicio»: al elegir el carné, explica el caso y pide una confirmación expresa (dos pasos).
 * - «final»: antes de guardar, muestra el cambio exacto y pide confirmarlo una última vez.
 */
const props = defineProps<{
  modo: 'inicio' | 'final' | null
  dniActual: string
  carneNuevo: string
}>()
const emit = defineEmits<{ confirmar: []; cancelar: [] }>()

const paso = ref<1 | 2>(1)
const entendido = ref(false)

watch(
  () => props.modo,
  () => {
    paso.value = 1
    entendido.value = false
  },
)

const titulos = {
  1: 'Cambiar a carné de extranjería',
  2: 'Revisa antes de continuar',
  final: '¿Confirmas el cambio de tu documento?',
}
</script>

<template>
  <BaseDialogo
    :abierto="modo !== null"
    :titulo="modo === 'final' ? titulos.final : titulos[paso]"
    @cerrar="emit('cancelar')"
  >
    <template #icono>
      <BaseIcono nombre="alerta" class="size-5" />
    </template>

    <template v-if="modo === 'inicio' && paso === 1">
      <p class="mt-2 text-[13px] text-secundario">
        Tu documento identifica a la persona titular de esta cuenta y no se puede cambiar por el de
        otra persona. Solo puedes pasar de tu DNI a un carné de extranjería si ahora te identificas
        con él, por ejemplo, tras un cambio de residencia.
      </p>
      <p class="mt-3 rounded-lg bg-aviso-fondo p-3 text-[13px] text-aviso">
        Si tu DNI tiene un error, no lo cambies aquí: pide ayuda a soporte.
      </p>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" @click="emit('cancelar')">Mantener mi DNI</BaseBoton>
        <BaseBoton @click="paso = 2">Entiendo, continuar</BaseBoton>
      </div>
    </template>

    <template v-else-if="modo === 'inicio'">
      <ul class="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[13px] text-secundario">
        <li>Tus registros y decisiones seguirán a tu nombre, identificados con el carné.</li>
        <li>No podrás volver a tu DNI desde Mi cuenta.</li>
        <li>Para guardar te pediremos tu contraseña y una última confirmación.</li>
      </ul>
      <label class="mt-5 flex cursor-pointer items-start gap-3 rounded-lg border border-borde p-3">
        <input
          v-model="entendido"
          type="checkbox"
          class="mt-0.5 size-4 accent-[var(--color-acento)]"
        />
        <span class="text-[13px]">
          Confirmo que el carné de extranjería es mío y que reemplaza a mi DNI.
        </span>
      </label>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" @click="emit('cancelar')">Mantener mi DNI</BaseBoton>
        <BaseBoton :deshabilitado="!entendido" @click="emit('confirmar')">
          Cambiar a carné
        </BaseBoton>
      </div>
    </template>

    <template v-else-if="modo === 'final'">
      <p class="mt-2 text-[13px] text-secundario">
        Es el último paso. Al guardar, tu cuenta quedará identificada con el carné.
      </p>
      <dl
        class="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg bg-fondo p-4 text-[13px]"
      >
        <dt class="text-secundario">Antes</dt>
        <dd class="font-bold">DNI {{ dniActual }}</dd>
        <dt class="text-secundario">Después</dt>
        <dd class="font-bold break-all">Carné de extranjería {{ carneNuevo }}</dd>
      </dl>
      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseBoton variante="secundario" @click="emit('cancelar')">Revisar</BaseBoton>
        <BaseBoton @click="emit('confirmar')">Sí, cambiar mi documento</BaseBoton>
      </div>
    </template>
  </BaseDialogo>
</template>
