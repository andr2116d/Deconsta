<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'

import DialogoConfirmarRegla from '../components/DialogoConfirmarRegla.vue'
import DialogoTitular from '../components/DialogoTitular.vue'
import ProbadorReglas from '../components/ProbadorReglas.vue'
import TarjetaLimite from '../components/TarjetaLimite.vue'
import TitularesAutorizados from '../components/TitularesAutorizados.vue'
import { useReglasStore } from '../stores/reglas'
import type { Titular } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const store = useReglasStore()

// Diálogo del titular: abierto para agregar (null) o para editar uno.
const dialogo = ref<{ titular: Titular | null } | null>(null)
const porQuitar = ref<Titular | null>(null)
const ocupado = ref<string | null>(null)
const aviso = ref<string | null>(null)
const fallo = ref<ErrorApi | null>(null)

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

async function cargar() {
  try {
    await store.cargar()
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  }
}

function alGuardarTitular(titular: Titular, agregado: boolean) {
  dialogo.value = null
  aviso.value = agregado
    ? `Agregaste a ${titular.nombre}: sus recibos ya no pedirán tu autorización por estar a otro nombre.`
    : `Guardaste los cambios de ${titular.nombre}.`
}

async function quitar(motivo: string | null) {
  const titular = porQuitar.value
  if (!titular) return
  ocupado.value = titular.id
  aviso.value = null
  try {
    await store.quitarTitular(titular.id, motivo)
    aviso.value = `Quitaste a ${titular.nombre}: sus recibos volverán a pedir tu autorización.`
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
    else {
      fallo.value =
        error instanceof ErrorApi
          ? error
          : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
    }
  } finally {
    porQuitar.value = null
    ocupado.value = null
  }
}

onMounted(() => {
  // Nunca se ven, ni por un instante, las reglas de otra sesión.
  store.olvidar()
  void cargar()
})
</script>

<template>
  <div>
    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>

    <div v-if="store.errorCarga && !store.reglas" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" titulo="No pudimos cargar tus reglas" class="w-full">
        {{
          store.errorCarga instanceof ErrorApi
            ? store.errorCarga.message
            : 'Ocurrió un error inesperado.'
        }}
      </BaseAviso>
      <BaseBoton variante="secundario" :cargando="store.cargando" @click="cargar">
        Reintentar
      </BaseBoton>
    </div>

    <div
      v-else-if="!store.reglas"
      aria-hidden="true"
      class="grid gap-6 motion-safe:animate-pulse lg:grid-cols-[minmax(0,1fr)_300px]"
    >
      <div class="flex flex-col gap-4">
        <div class="h-[250px] rounded-[14px] border border-borde bg-white" />
        <div class="h-[220px] rounded-[14px] border border-borde bg-white" />
      </div>
      <div class="h-[320px] rounded-[14px] border border-borde bg-white" />
    </div>

    <div v-else class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
      <div class="flex min-w-0 flex-col gap-6">
        <TarjetaLimite
          @guardado="(mensaje) => (aviso = mensaje)"
          @sesion-terminada="sesionTerminada"
        />
        <TitularesAutorizados
          :titulares="store.reglas.titulares"
          :maximo="store.reglas.maximo_titulares"
          :nombre-gerente="sesion.usuario?.nombres ?? ''"
          :ocupado="ocupado"
          @agregar="dialogo = { titular: null }"
          @editar="(titular) => (dialogo = { titular })"
          @quitar="(titular) => (porQuitar = titular)"
        />
      </div>

      <aside class="flex flex-col gap-4 self-start">
        <ProbadorReglas @sesion-terminada="sesionTerminada" />
        <div class="rounded-[14px] bg-fondo p-5 text-[13px] text-secundario">
          <h2 class="text-[15px] font-extrabold text-tinta">Lo que espere tu autorización</h2>
          <p class="mt-1.5">
            Cuando se registren deudas, llegará a «Por autorizar» con su motivo. Al aceptarla pasa
            al calendario y a los pendientes de tu asistente; mientras tanto, no se puede pagar.
          </p>
          <p class="mt-3">
            Al leer cada recibo, Deconsta también revisará que no se haya registrado antes y que un
            comprobante de pago no se use dos veces.
          </p>
        </div>
      </aside>
    </div>

    <DialogoTitular
      :abierto="dialogo !== null"
      :titular="dialogo?.titular"
      @guardado="alGuardarTitular"
      @cerrar="dialogo = null"
      @sesion-terminada="sesionTerminada"
    />
    <DialogoConfirmarRegla
      :abierto="porQuitar !== null"
      :titulo="porQuitar ? `¿Quitar a ${porQuitar.nombre}?` : ''"
      :puntos="[
        'Sus recibos volverán a esperar tu autorización por estar a otro nombre.',
        'Lo ya registrado no cambia, y queda constancia en el historial.',
      ]"
      confirmar="Quitar titular"
      :enviando="ocupado !== null"
      con-motivo
      @confirmar="quitar"
      @cancelar="porQuitar = null"
    />
    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos quitar el titular"
      :etiquetas="{}"
      @cerrar="fallo = null"
      @reintentar="
        () => {
          fallo = null
          void cargar()
        }
      "
    />
  </div>
</template>
