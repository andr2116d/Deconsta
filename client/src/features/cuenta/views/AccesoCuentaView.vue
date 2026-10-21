<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import FormularioCambioContrasena from '@/features/acceso/components/FormularioCambioContrasena.vue'
import { useSesionStore } from '@/features/acceso/stores/sesion'
import BaseAviso from '@/shared/components/BaseAviso.vue'

import FormularioNombreUsuario from '../components/FormularioNombreUsuario.vue'
import TarjetaCuenta from '../components/TarjetaCuenta.vue'
import { formatearFecha } from '../datos'
import { useCuentaStore } from '../stores/cuenta'

const router = useRouter()
const sesion = useSesionStore()
const cuenta = useCuentaStore()
const contrasenaCambiada = ref(false)

const actualizada = computed(() =>
  cuenta.cuenta ? formatearFecha(cuenta.cuenta.contrasena_actualizada_en) : '',
)

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

async function alCambiarContrasena() {
  contrasenaCambiada.value = true
  // La fecha de actualización y el indicador de contraseña temporal vienen de la API.
  await cuenta.cargar().catch(() => undefined)
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <TarjetaCuenta
      titulo="Usuario de acceso"
      descripcion="Tu usuario identifica tu cuenta al ingresar."
      :cargando="!cuenta.cuenta"
    >
      <FormularioNombreUsuario
        v-if="cuenta.cuenta"
        :cuenta="cuenta.cuenta"
        @sesion-terminada="sesionTerminada"
      />
    </TarjetaCuenta>

    <TarjetaCuenta
      titulo="Contraseña"
      descripcion="Al cambiarla se cerrarán tus otras sesiones abiertas."
      :cargando="!cuenta.cuenta"
    >
      <template v-if="cuenta.cuenta">
        <div class="mb-6 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[10px] bg-fondo p-4">
          <span aria-hidden="true" class="text-[18px] tracking-[0.2em] text-tinta">••••••••••</span>
          <p class="text-[12px] text-secundario">
            <span class="sr-only">Tu contraseña está oculta. </span>
            Actualizada el {{ actualizada }}.
            <span class="block">
              Se guarda cifrada de forma irreversible: nadie puede verla, ni siquiera Deconsta.
            </span>
          </p>
        </div>
        <BaseAviso
          v-if="cuenta.cuenta.debe_cambiar_contrasena"
          tono="aviso"
          titulo="Sigues usando la contraseña temporal"
          class="mb-5"
        >
          Reemplázala por una que solo tú conozcas.
        </BaseAviso>
        <BaseAviso v-if="contrasenaCambiada" tono="exito" class="mb-5">
          Contraseña actualizada. Ya puedes usarla en tus próximos ingresos.
        </BaseAviso>
        <div class="max-w-[440px]">
          <FormularioCambioContrasena
            :inicial="cuenta.cuenta.debe_cambiar_contrasena"
            @cambiada="alCambiarContrasena"
            @sesion-terminada="sesionTerminada"
          />
        </div>
      </template>
    </TarjetaCuenta>
  </div>
</template>
