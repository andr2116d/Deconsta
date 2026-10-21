<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'

import PestanasSeccion from '@/features/espacio/components/PestanasSeccion.vue'

import PaseCuenta from '../components/PaseCuenta.vue'
import { useCuentaStore } from '../stores/cuenta'

// Marco de «Mi cuenta»: el encabezado, las pestañas y la tarjeta lateral se quedan; solo cambia
// el contenido de la pestaña.
const router = useRouter()
const sesion = useSesionStore()
const cuenta = useCuentaStore()

async function cargar() {
  try {
    await cuenta.cargar()
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      sesion.olvidar()
      router.replace({ name: 'inicio-sesion' })
    }
  }
}

onMounted(cargar)
</script>

<template>
  <section v-if="sesion.usuario" aria-labelledby="titulo-seccion">
    <header class="mb-5 sm:mb-6">
      <h1
        id="titulo-seccion"
        tabindex="-1"
        class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
      >
        Tu cuenta, a tu nombre.
      </h1>
      <p class="mt-2 text-[13px] text-secundario">
        Actualiza tu información y consulta qué puede hacer tu rol.
      </p>
    </header>

    <PestanasSeccion grupo="cuenta" :rol="sesion.usuario.rol" etiqueta="Secciones de Mi cuenta" />

    <div
      class="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-8 xl:grid-cols-[290px_minmax(0,760px)] xl:gap-10"
    >
      <PaseCuenta :cuenta="cuenta.cuenta" />

      <div class="min-w-0">
        <div
          v-if="cuenta.errorCarga && !cuenta.cuenta"
          class="mb-6 flex flex-col items-start gap-3"
        >
          <BaseAviso tono="error" titulo="No pudimos cargar tu cuenta" class="w-full">
            {{
              cuenta.errorCarga instanceof ErrorApi
                ? cuenta.errorCarga.message
                : 'Ocurrió un error inesperado.'
            }}
          </BaseAviso>
          <BaseBoton variante="secundario" :cargando="cuenta.cargando" @click="cargar">
            Reintentar
          </BaseBoton>
        </div>

        <RouterView v-slot="{ Component, route: actual }">
          <Transition name="vista" mode="out-in">
            <component :is="Component" :key="actual.name" />
          </Transition>
        </RouterView>
      </div>
    </div>
  </section>
</template>
