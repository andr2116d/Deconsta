<script setup lang="ts">
import { computed, ref } from 'vue'

import { formatearSoles } from '@/features/reglas/importes'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import { anularDeuda, autorizarDeuda, darVistoBueno, rechazarDeuda } from '../api/deudas'
import {
  CAMPOS_CORREGIDOS,
  ESTADOS,
  formatearFecha,
  MOTIVOS,
  nombresLugares,
  textoVencida,
  TIPOS_DOCUMENTO,
} from '../catalogo'
import type { DeudaDetalle } from '../types'
import DialogoMotivo from './DialogoMotivo.vue'
import ResultadoAnalisis from './ResultadoAnalisis.vue'
import VistaDocumento from './VistaDocumento.vue'

/**
 * La mesa de decisión del gerente: el documento, por qué espera, qué se corrigió y la acción.
 * Las acciones las autoriza el backend; aquí solo se ofrecen las que corresponden al estado.
 */
const props = defineProps<{ deuda: DeudaDetalle; categoria: string | null }>()
const emit = defineEmits<{
  decidida: [deuda: DeudaDetalle, mensaje: string]
  'sesion-terminada': []
}>()

const ocupada = ref(false)
const fallo = ref<string | null>(null)
const motivo = ref<'rechazar' | 'anular' | null>(null)
const errorMotivo = ref<string | undefined>()

const espera = computed(() => props.deuda.estado === 'por_autorizar')
const pregunta = computed(() => {
  if (!espera.value) return 'Ya se puede pagar. Dale tu visto bueno o anúlala si no corresponde.'
  if (props.deuda.motivos.includes('TITULAR_DISTINTO'))
    return 'El titular no eres tú ni uno de tus titulares autorizados. ¿Este gasto es de tu espacio?'
  if (props.deuda.motivos.includes('IMPORTE_SOBRE_LIMITE'))
    return 'Supera tu límite. ¿Autorizas que se pague?'
  return 'El documento o sus datos necesitan tu revisión antes de pagarse.'
})

const propuesta = computed(() => props.deuda.documento?.propuesta ?? null)
const corregidos = computed(() =>
  props.deuda.campos_corregidos.map((campo) => {
    const leido = propuesta.value
    const valores: Record<string, [string | null | undefined, string | null]> = {
      importe: [
        leido?.importe && formatearSoles(leido.importe),
        formatearSoles(props.deuda.importe),
      ],
      vencimiento: [
        leido?.vence_el && formatearFecha(leido.vence_el),
        formatearFecha(props.deuda.vence_el),
      ],
      codigo_pago: [leido?.codigo_pago, props.deuda.codigo_pago],
      titular: [leido?.titular_nombre, props.deuda.titular_nombre],
    }
    const [documento, registrado] = valores[campo] ?? [null, null]
    return { campo, etiqueta: CAMPOS_CORREGIDOS[campo] ?? campo, documento, registrado }
  }),
)

async function ejecutar(accion: () => Promise<DeudaDetalle>, mensaje: string) {
  if (ocupada.value) return
  ocupada.value = true
  fallo.value = null
  errorMotivo.value = undefined
  try {
    const decidida = await accion()
    motivo.value = null
    emit('decidida', decidida, mensaje)
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
      emit('sesion-terminada')
      return
    }
    const texto = error instanceof ErrorApi ? error.message : 'Ocurrió un error inesperado.'
    if (motivo.value && error instanceof ErrorApi && error.campos.motivo) {
      errorMotivo.value = error.campos.motivo
    } else {
      motivo.value = null
      fallo.value = texto
    }
  } finally {
    ocupada.value = false
  }
}

const id = computed(() => props.deuda.id)
const autorizar = () =>
  ejecutar(
    () => autorizarDeuda(id.value),
    `Autorizaste «${props.deuda.concepto}». Ya se puede pagar.`,
  )
const vistoBueno = () =>
  ejecutar(() => darVistoBueno(id.value), `Diste tu visto bueno a «${props.deuda.concepto}».`)
function confirmarMotivo(texto: string) {
  const accion = motivo.value
  if (accion === 'rechazar')
    void ejecutar(() => rechazarDeuda(id.value, texto), `Rechazaste «${props.deuda.concepto}».`)
  if (accion === 'anular')
    void ejecutar(() => anularDeuda(id.value, texto), `Anulaste «${props.deuda.concepto}».`)
}
</script>

<template>
  <article
    class="grid animate-aparecer gap-6 rounded-[14px] border border-borde bg-white p-5 sm:p-6 xl:grid-cols-[minmax(240px,0.8fr)_minmax(0,1.2fr)]"
    :aria-labelledby="`deuda-${deuda.id}`"
  >
    <div>
      <VistaDocumento
        :documento-id="deuda.documento_id"
        :tipo="deuda.documento?.tipo_archivo ?? 'application/pdf'"
        :titulo="`Documento de ${deuda.concepto}`"
      />
      <p class="mt-3 text-center text-[11px] text-secundario">
        {{ TIPOS_DOCUMENTO[deuda.tipo_documento] }} que subió {{ deuda.registrada_por.nombre }}
      </p>
      <div v-if="deuda.documento" class="mt-5">
        <ResultadoAnalisis :documento="deuda.documento" :revisando="false" />
      </div>
    </div>

    <!-- En pantallas angostas la decisión va primero; el documento, después. -->
    <div class="order-first min-w-0 xl:order-none">
      <div class="flex flex-wrap items-center justify-between gap-2 text-[11px] text-secundario">
        <span
          class="inline-flex rounded-md px-2 py-0.5 font-bold"
          :class="ESTADOS[deuda.estado].clase"
        >
          {{ espera ? 'Solo tú puedes autorizarla' : 'Revisión pendiente' }}
        </span>
        <span v-if="deuda.vencida_hace" class="font-bold text-error">
          {{ textoVencida(deuda.vencida_hace) }} · {{ formatearFecha(deuda.vence_el) }}
        </span>
        <span v-else>Vence el {{ formatearFecha(deuda.vence_el) }}</span>
      </div>
      <h2
        :id="`deuda-${deuda.id}`"
        class="mt-3 text-[22px] leading-tight font-extrabold tracking-[-0.02em]"
      >
        {{ deuda.concepto }}
      </h2>
      <p class="mt-2 max-w-[480px] text-[13px] leading-relaxed text-secundario">{{ pregunta }}</p>
      <p class="mt-4 text-[34px] leading-none font-extrabold tracking-[-0.03em]">
        {{ formatearSoles(deuda.importe) }}
      </p>
      <p v-if="deuda.cuotas.length > 1" class="mt-1 text-[12px] text-secundario">
        En {{ deuda.cuotas.length }} cuotas, la primera el
        {{ formatearFecha(deuda.cuotas[0]!.vence_el) }}
      </p>

      <ul v-if="deuda.motivos.length" class="mt-4 flex flex-wrap gap-2">
        <li
          v-for="m in deuda.motivos"
          :key="m"
          class="rounded-full bg-aviso-fondo px-3 py-1 text-[12px] font-bold text-aviso"
        >
          {{ MOTIVOS[m] }}
        </li>
      </ul>

      <dl class="mt-5 grid gap-x-5 gap-y-3 text-[12px] sm:grid-cols-2">
        <div>
          <dt class="text-[11px] text-secundario">Lo registró</dt>
          <dd class="font-bold">{{ deuda.registrada_por.nombre }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Categoría</dt>
          <dd class="font-bold">{{ categoria ?? 'Otros' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Titular del documento</dt>
          <dd class="font-bold">
            {{ deuda.titular_nombre ?? 'No figura' }}
            <span v-if="deuda.titular_documento" class="font-normal text-secundario">
              · {{ deuda.titular_documento }}
            </span>
          </dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Código de pago</dt>
          <dd class="font-bold">{{ deuda.codigo_pago ?? 'No figura' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] text-secundario">Se puede pagar en</dt>
          <dd class="font-bold">{{ nombresLugares(deuda.lugares_pago) }}</dd>
        </div>
      </dl>

      <section v-if="corregidos.length" class="mt-5 rounded-[10px] bg-fondo p-4">
        <h3 class="text-[13px] font-extrabold">Corregido a mano</h3>
        <p class="mt-0.5 text-[12px] text-secundario">
          Lo que dice el documento y lo que se registró.
        </p>
        <table class="mt-3 w-full text-left text-[12px]">
          <thead class="text-[11px] text-secundario">
            <tr>
              <th scope="col" class="font-bold">Dato</th>
              <th scope="col" class="font-bold">Documento</th>
              <th scope="col" class="font-bold">Registrado</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fila in corregidos" :key="fila.campo" class="border-t border-borde">
              <th scope="row" class="py-2 pr-2 font-bold">{{ fila.etiqueta }}</th>
              <td class="py-2 pr-2 text-secundario">{{ fila.documento || 'No se leyó' }}</td>
              <td class="py-2 font-bold">{{ fila.registrado || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <BaseAviso v-if="fallo" tono="error" class="mt-5">{{ fallo }}</BaseAviso>

      <div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
        <template v-if="espera">
          <BaseBoton variante="secundario" :deshabilitado="ocupada" @click="motivo = 'rechazar'">
            Rechazar
          </BaseBoton>
          <BaseBoton :cargando="ocupada && !motivo" @click="autorizar">
            Autorizar deuda
            <BaseIcono nombre="check" class="size-4" />
          </BaseBoton>
        </template>
        <template v-else>
          <BaseBoton variante="secundario" :deshabilitado="ocupada" @click="motivo = 'anular'">
            Anular
          </BaseBoton>
          <BaseBoton :cargando="ocupada && !motivo" @click="vistoBueno">
            Dar visto bueno
            <BaseIcono nombre="check" class="size-4" />
          </BaseBoton>
        </template>
      </div>
    </div>

    <DialogoMotivo
      :abierto="motivo !== null"
      :accion="motivo ?? 'rechazar'"
      :concepto="deuda.concepto"
      :enviando="ocupada"
      :error="errorMotivo"
      @confirmar="confirmarMotivo"
      @cerrar="motivo = null"
    />
  </article>
</template>
