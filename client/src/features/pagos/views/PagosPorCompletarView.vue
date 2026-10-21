<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { diasEntre } from '@/features/calendario/fechas'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import { formatearFecha } from '@/features/deudas/catalogo'
import { useNotificacionesStore } from '@/features/notificaciones/stores/notificaciones'
import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { listarPagos, listarPorPagar } from '../api/pagos'
import TarjetaCuotaPorPagar from '../components/TarjetaCuotaPorPagar.vue'
import type { Pago, PorPagar } from '../types'

/** Lo que falta pagar en el espacio, lo más urgente primero, y lo que espera la verificación. */
const router = useRouter()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const notificaciones = useNotificacionesStore()

const porPagar = ref<PorPagar | null>(null)
const enVerificacion = ref<Pago[]>([])
const fallo = ref(false)
const cargando = ref(false)
const DIAS_SEMANA = 7
const gerente = computed(() => sesion.usuario?.rol === 'gerente')

const grupos = computed(() => {
  const datos = porPagar.value
  if (!datos) return []
  const vencidas = datos.cuotas.filter((c) => c.vencida_hace !== null)
  const pronto = datos.cuotas.filter(
    (c) => c.vencida_hace === null && diasEntre(datos.hoy, c.vence_el) <= DIAS_SEMANA,
  )
  const despues = datos.cuotas.filter(
    (c) => c.vencida_hace === null && diasEntre(datos.hoy, c.vence_el) > DIAS_SEMANA,
  )
  return [
    { clave: 'vencidas', titulo: 'Vencidas', detalle: 'Págalas cuanto antes.', lista: vencidas },
    { clave: 'pronto', titulo: 'Vencen esta semana', detalle: '', lista: pronto },
    { clave: 'despues', titulo: 'Más adelante', detalle: '', lista: despues },
  ].filter((g) => g.lista.length)
})
const total = computed(() =>
  (porPagar.value?.cuotas ?? []).reduce((suma, c) => suma + Number(c.importe), 0),
)
const categoriaDe = (id: string | null) => categorias.categorias?.find((c) => c.id === id)

async function cargar() {
  cargando.value = true
  fallo.value = false
  try {
    const [cuotas, pagos] = await Promise.all([listarPorPagar(), listarPagos()])
    porPagar.value = cuotas
    enVerificacion.value = pagos.filter((p) => p.estado === 'por_verificar')
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      sesion.olvidar()
      router.replace({ name: 'inicio-sesion' })
      return
    }
    fallo.value = true
  } finally {
    cargando.value = false
  }
}

onMounted(() => {
  void cargar()
  if (!categorias.categorias) categorias.cargar().catch(() => undefined)
})
// Un aviso nuevo (un bloqueo levantado, una deuda autorizada) puede cambiar lo que falta pagar.
watch(
  () => notificaciones.avisos,
  () => void cargar(),
)
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-2 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Lo que falta pagar.
        </h1>
        <p class="mt-2 max-w-[62ch] text-[13px] text-secundario">
          <template v-if="gerente">
            Págalo tú mismo o pide a una asistente que lo pague: le saldrá un aviso hasta que
            registre el comprobante.
          </template>
          <template v-else>
            Paga fuera de Deconsta (en un agente, por Yape, en la banca por internet) y deja aquí el
            comprobante. Tu gerente lo verificará.
          </template>
        </p>
      </div>
      <p v-if="porPagar?.cuotas.length" class="text-[13px] text-secundario">
        {{ porPagar.cuotas.length }} por pagar ·
        <strong class="text-tinta">{{ formatearSoles(total) }}</strong>
      </p>
    </header>

    <BaseAviso
      v-if="porPagar?.registro_bloqueado"
      tono="error"
      titulo="Tu registro de pagos está en pausa"
      class="mb-6"
    >
      Varios comprobantes no correspondían a sus cuotas. Tu gerente ya recibió un aviso y puede
      permitirte registrar pagos otra vez. Mientras tanto, puedes seguir con lo demás.
    </BaseAviso>

    <div v-if="fallo && !porPagar" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" titulo="No pudimos cargar lo que falta pagar" class="w-full">
        Revisa tu conexión y vuelve a intentarlo.
      </BaseAviso>
      <BaseBoton variante="secundario" :cargando="cargando" @click="cargar">
        Volver a intentar
      </BaseBoton>
    </div>

    <div
      v-else-if="!porPagar"
      aria-hidden="true"
      class="flex flex-col gap-3 motion-safe:animate-pulse"
    >
      <div v-for="n in 3" :key="n" class="h-[104px] rounded-[14px] border border-borde bg-white" />
    </div>

    <div
      v-else-if="!porPagar.cuotas.length"
      class="flex flex-col items-center rounded-[14px] border border-dashed border-borde bg-white px-6 py-12 text-center"
    >
      <span
        aria-hidden="true"
        class="grid size-14 place-items-center rounded-[16px] bg-exito-fondo text-exito motion-safe:animate-flotar"
      >
        <BaseIcono nombre="check" class="size-6" />
      </span>
      <p class="mt-5 text-[18px] font-extrabold">Nada por pagar.</p>
      <p class="mt-2 max-w-[44ch] text-[13px] text-secundario">
        Cuando se registre una deuda, su próxima cuota aparecerá aquí con su vencimiento.
      </p>
    </div>

    <div v-else class="flex flex-col gap-7">
      <section v-for="grupo in grupos" :key="grupo.clave" :aria-labelledby="`grupo-${grupo.clave}`">
        <h2
          :id="`grupo-${grupo.clave}`"
          class="mb-2.5 text-[12px] font-bold"
          :class="grupo.clave === 'vencidas' ? 'text-error' : 'text-secundario'"
        >
          {{ grupo.titulo }} · {{ grupo.lista.length }}
          <span v-if="grupo.detalle" class="font-normal">— {{ grupo.detalle }}</span>
        </h2>
        <ul class="flex flex-col gap-2.5">
          <li v-for="cuota in grupo.lista" :key="`${cuota.deuda_id}-${cuota.cuota}`">
            <TarjetaCuotaPorPagar
              :cuota="cuota"
              :hoy="porPagar.hoy"
              :categoria="categoriaDe(cuota.categoria_id)"
              :bloqueado="porPagar.registro_bloqueado"
              :gerente="gerente"
              @cambio="cargar"
            />
          </li>
        </ul>
      </section>
    </div>

    <section
      v-if="enVerificacion.length"
      class="mt-9 rounded-[14px] bg-fondo p-5"
      aria-labelledby="titulo-verificacion"
    >
      <h2 id="titulo-verificacion" class="text-[15px] font-extrabold">
        {{ gerente ? 'Esperan tu verificación' : 'Esperan la verificación del gerente' }} ·
        {{ enVerificacion.length }}
      </h2>
      <ul class="mt-3 flex flex-col divide-y divide-borde">
        <li
          v-for="pago in enVerificacion"
          :key="pago.id"
          class="flex items-center justify-between gap-3 py-2.5 text-[13px]"
        >
          <span class="min-w-0">
            <strong class="block truncate">{{ pago.concepto }}</strong>
            <small class="text-[11px] text-secundario">
              Pagó {{ pago.registrado_por }} el {{ formatearFecha(pago.pagado_el) }}
            </small>
          </span>
          <strong class="shrink-0">{{ formatearSoles(pago.importe) }}</strong>
        </li>
      </ul>
    </section>
  </section>
</template>
