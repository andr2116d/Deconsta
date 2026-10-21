<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import DialogoCredenciales from '../components/DialogoCredenciales.vue'
import FormularioAsistente from '../components/FormularioAsistente.vue'
import type { Credenciales } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const credenciales = ref<Credenciales | null>(null)
const recuperada = ref(false)

function alCrear(nuevas: Credenciales, fueRecuperada: boolean) {
  credenciales.value = nuevas
  recuperada.value = fueRecuperada
}

function volverAlEquipo() {
  const nombre = credenciales.value
    ? `${credenciales.value.asistente.nombres} ${credenciales.value.asistente.apellidos}`
    : ''
  const aviso = recuperada.value
    ? `Recuperaste la cuenta de ${nombre}.`
    : `${nombre} ya es parte de tu equipo.`
  credenciales.value = null
  router.push({ name: 'equipo', state: { aviso } })
}

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <nav aria-label="Ruta" class="mb-4 text-[12px] text-secundario">
      <ol class="flex items-center gap-1.5">
        <li>
          <RouterLink :to="{ name: 'equipo' }" class="font-bold text-acento hover:underline">
            Mi equipo
          </RouterLink>
        </li>
        <li aria-hidden="true"><BaseIcono nombre="derecha" class="size-3.5" /></li>
        <li aria-current="page">Registrar asistente</li>
      </ol>
    </nav>
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      Dale un lugar en tu equipo.
    </h1>
    <p class="mt-2 mb-6 text-[13px] text-secundario sm:mb-8">
      Completa sus datos y define cómo entrará a Deconsta.
    </p>

    <div
      class="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-8 xl:grid-cols-[290px_minmax(0,760px)]"
    >
      <aside
        class="self-start rounded-[14px] bg-[#e0eae3] p-5 text-[#254436] lg:sticky lg:top-[156px] lg:p-6"
      >
        <span
          aria-hidden="true"
          class="grid size-12 place-items-center rounded-full bg-white text-[#365c4b]"
        >
          <BaseIcono nombre="equipo" class="size-6" />
        </span>
        <h2 class="mt-4 text-[20px] font-extrabold">Nueva asistente</h2>
        <span
          class="mt-2 inline-flex rounded-md bg-[#365c4b] px-2.5 py-1 text-[11px] font-bold text-white"
        >
          Rol fijo · Asistente
        </span>
        <p class="mt-3 text-[13px]">
          Podrá registrar deudas, consultar sus encargos y adjuntar comprobantes.
        </p>
        <dl class="mt-4 text-[12px]">
          <div class="border-t border-[#365c4b]/15 py-3">
            <dt class="opacity-75">Las autorizaciones</dt>
            <dd class="font-bold">Seguirán a tu cargo</dd>
          </div>
          <div class="border-t border-[#365c4b]/15 py-3">
            <dt class="opacity-75">En su primer ingreso</dt>
            <dd class="font-bold">
              Aceptará las políticas, cambiará su contraseña y confirmará sus datos
            </dd>
          </div>
        </dl>
      </aside>

      <div class="rounded-[14px] border border-borde bg-white p-5 sm:p-7">
        <FormularioAsistente @creada="alCrear" @sesion-terminada="sesionTerminada">
          <template #cancelar>
            <RouterLink
              :to="{ name: 'equipo' }"
              class="inline-flex min-h-11 items-center justify-center rounded-[9px] px-4 text-[13px] font-bold text-acento transition-colors duration-200 hover:bg-acento-suave"
            >
              Cancelar
            </RouterLink>
          </template>
        </FormularioAsistente>
      </div>
    </div>

    <DialogoCredenciales
      :credenciales="credenciales"
      :recuperada="recuperada"
      @cerrar="volverAlEquipo"
    />
  </section>
</template>
