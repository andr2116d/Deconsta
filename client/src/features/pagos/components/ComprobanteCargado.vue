<script setup lang="ts">
import { computed, ref } from 'vue'

import { formatearFecha, LUGARES_PAGO } from '@/features/deudas/catalogo'
import type { Riesgo } from '@/features/deudas/types'
import { formatearSoles } from '@/features/reglas/importes'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import type { Voucher } from '../composables/useComprobantes'
import type { Comprobante } from '../types'
import DatosAMano from './DatosAMano.vue'

/**
 * Un voucher subido: cómo va su revisión, lo que leímos y, si no sirve, por qué. Lo que muestra
 * orienta; el backend decide con las mismas señales al registrar el pago.
 */
const props = defineProps<{
  voucher: Voucher
  numero: number
  bloqueado?: boolean
  /** Para escribir a mano los datos de un voucher que no se pudo leer: la cuota y el día. */
  importe?: string
  hoy?: string
}>()
const emit = defineEmits<{
  quitar: []
  'declarar-mora': []
  completado: [comprobante: Comprobante]
}>()

const escribiendo = ref(false)

type Tono = 'proceso' | 'bien' | 'aviso' | 'mal'

const ESTADOS: Record<string, { texto: string; tono: Tono; icono: NombreIcono }> = {
  subiendo: { texto: 'Subiendo…', tono: 'proceso', icono: 'reloj' },
  analizando: { texto: 'Revisando…', tono: 'proceso', icono: 'reloj' },
  listo: { texto: 'Listo', tono: 'bien', icono: 'check' },
  ilegible: { texto: 'No se lee', tono: 'aviso', icono: 'alerta' },
  rechazado: { texto: 'No corresponde', tono: 'mal', icono: 'cerrar' },
  repetido: { texto: 'Ya se usó', tono: 'mal', icono: 'cerrar' },
  fallido: { texto: 'Sin revisar', tono: 'aviso', icono: 'alerta' },
  error: { texto: 'No se subió', tono: 'mal', icono: 'cerrar' },
}
const TONOS: Record<Tono, string> = {
  proceso: 'bg-fondo text-secundario',
  bien: 'bg-exito-fondo text-exito',
  aviso: 'bg-aviso-fondo text-aviso',
  mal: 'bg-error-fondo text-error',
}
const RIESGOS: Record<Riesgo, string> = {
  bajo: 'text-secundario',
  medio: 'text-aviso',
  alto: 'text-error',
}

const comprobante = computed(() => props.voucher.comprobante)
const clave = computed(() => {
  const { etapa } = props.voucher
  if (etapa !== 'terminado') return etapa
  return comprobante.value?.estado ?? 'fallido'
})
const estado = computed(() => ESTADOS[clave.value] ?? ESTADOS.fallido!)
const esImagen = computed(() => props.voucher.archivo.type.startsWith('image/'))
const lectura = computed(() => comprobante.value?.lectura ?? null)
const lugar = computed(
  () => LUGARES_PAGO.find((l) => l.valor === lectura.value?.lugar)?.etiqueta ?? null,
)
const resumen = computed(() => {
  const leido = lectura.value
  if (!leido) return null
  return [
    leido.medio ?? lugar.value,
    leido.pagado_el && formatearFecha(leido.pagado_el),
    leido.numero_operacion && `Operación ${leido.numero_operacion}`,
  ]
    .filter(Boolean)
    .join(' · ')
})
const detalle = computed(() => {
  if (props.voucher.etapa === 'error') return props.voucher.error?.message ?? null
  if (clave.value === 'fallido' && !escribiendo.value)
    return 'No pudimos leerlo solo. Escribe sus datos o quítalo y súbelo otra vez.'
  return null
})
// Solo un voucher de pago que falló al leerse se completa a mano.
const completable = computed(
  () =>
    clave.value === 'fallido' &&
    comprobante.value?.proposito === 'pago' &&
    props.importe !== undefined &&
    props.hoy !== undefined,
)
const aMano = computed(
  () => comprobante.value?.senales.some((s) => s.codigo === 'DATOS_A_MANO') ?? false,
)
// Pagó por más en una cuota vencida: el voucher puede servir de prueba de la mora.
const posibleMora = computed(
  () => comprobante.value?.senales.some((s) => s.codigo === 'POSIBLE_MORA') ?? false,
)
// Lo que conviene que vea: primero lo que impide usarlo, después los avisos.
const senales = computed(() => {
  const orden: Record<Riesgo, number> = { alto: 0, medio: 1, bajo: 2 }
  return (comprobante.value?.senales ?? [])
    .filter((s) => s.codigo !== 'DATOS_A_MANO')
    .sort((a, b) => orden[a.riesgo] - orden[b.riesgo])
})
</script>

<template>
  <article
    class="animate-aparecer rounded-[12px] border bg-white p-3.5"
    :class="estado.tono === 'mal' ? 'border-error/40' : 'border-borde'"
    :aria-label="`Voucher ${numero}: ${estado.texto}`"
  >
    <div class="flex items-start gap-3">
      <span
        class="grid size-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-fondo text-secundario"
      >
        <img
          v-if="esImagen"
          :src="voucher.vista"
          alt=""
          class="size-full object-cover"
          :class="voucher.etapa === 'analizando' ? 'motion-safe:animate-pulse' : ''"
        />
        <BaseIcono v-else nombre="documento" class="size-6" />
      </span>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <strong class="text-[13px]">Voucher {{ numero }}</strong>
          <span
            class="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold"
            :class="TONOS[estado.tono]"
            role="status"
          >
            <span
              v-if="estado.tono === 'proceso'"
              aria-hidden="true"
              class="size-3 animate-girar rounded-full border-2 border-current border-t-transparent"
            />
            <BaseIcono v-else :nombre="estado.icono" class="size-3.5" />
            {{ estado.texto }}
          </span>
          <span
            v-if="lectura?.importe"
            class="ml-auto text-[14px] font-extrabold"
            :class="clave === 'listo' ? '' : 'text-secundario line-through'"
          >
            {{ formatearSoles(lectura.importe) }}
          </span>
        </div>
        <p class="mt-0.5 truncate text-[11px] text-secundario">
          {{ resumen || voucher.archivo.name }}
        </p>
        <p v-if="aMano" class="text-[11px] font-bold text-aviso">
          Datos escritos a mano: tu gerente revisará el voucher.
        </p>
        <p v-if="lectura?.comision" class="text-[11px] text-secundario">
          Más {{ formatearSoles(lectura.comision) }} de comisión, aparte.
        </p>
        <p
          v-if="voucher.demorado && voucher.etapa === 'analizando'"
          class="mt-1 text-[11px] text-secundario"
        >
          Está tardando un poco más: puede haber otros archivos en revisión.
        </p>
      </div>
    </div>

    <p v-if="detalle" class="mt-2.5 text-[12px] text-error">{{ detalle }}</p>
    <ul v-if="senales.length" class="mt-2.5 flex flex-col gap-1.5">
      <li
        v-for="senal in senales"
        :key="senal.codigo"
        class="flex gap-2 text-[12px] leading-snug"
        :class="RIESGOS[senal.riesgo]"
      >
        <BaseIcono
          :nombre="
            senal.riesgo === 'alto' ? 'cerrar' : senal.riesgo === 'medio' ? 'alerta' : 'destello'
          "
          class="mt-0.5 size-3.5 shrink-0"
        />
        <span>{{ senal.detalle }}</span>
      </li>
    </ul>

    <DatosAMano
      v-if="completable && escribiendo && comprobante && importe !== undefined && hoy"
      :comprobante-id="comprobante.id"
      :importe="importe"
      :hoy="hoy"
      @completado="(c) => emit('completado', c)"
    />

    <div class="mt-2 flex flex-wrap justify-end gap-2">
      <BaseBoton
        v-if="completable && !escribiendo"
        variante="secundario"
        :deshabilitado="bloqueado"
        @click="escribiendo = true"
      >
        Escribir los datos
      </BaseBoton>
      <BaseBoton
        v-if="posibleMora"
        variante="secundario"
        :deshabilitado="bloqueado"
        @click="emit('declarar-mora')"
      >
        Declarar la mora con este voucher
      </BaseBoton>
      <BaseBoton
        variante="discreto"
        :deshabilitado="bloqueado"
        :aria-label="`Quitar el voucher ${numero}`"
        @click="emit('quitar')"
      >
        Quitar
      </BaseBoton>
    </div>
  </article>
</template>
