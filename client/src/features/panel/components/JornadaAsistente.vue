<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { cuandoVence } from '@/features/calendario/fechas'
import InsigniaCategoria from '@/features/categorias/components/InsigniaCategoria.vue'
import type { Categoria } from '@/features/categorias/types'
import { formatearFecha, nombresLugares } from '@/features/deudas/catalogo'
import { formatearSoles } from '@/features/reglas/importes'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Jornada } from '../types'
import CifraPanel from './CifraPanel.vue'

/** La jornada de la asistente: su trabajo pendiente y su siguiente pago. */
defineProps<{
  jornada: Jornada
  hoy: string
  categoriaDe: (id: string | null) => Categoria | undefined
}>()

const primerNombre = (nombre: string) => nombre.split(' ')[0] ?? nombre
</script>

<template>
  <div class="flex flex-col gap-8">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <CifraPanel
        etiqueta="Pagos por completar"
        :valor="String(jornada.por_completar)"
        :destino="{ name: 'pagos-por-completar' }"
      />
      <CifraPanel
        etiqueta="Pagos devueltos"
        :valor="String(jornada.devueltas)"
        detalle="por volver a pagar"
        :destino="{ name: 'pagos-por-completar' }"
        :atencion="jornada.devueltas > 0"
      />
      <CifraPanel
        :etiqueta="`En manos de ${primerNombre(jornada.gerente)}`"
        :valor="String(jornada.en_manos_del_gerente)"
        detalle="deudas, pagos y moras"
        :destino="{ name: 'mis-registros' }"
      />
    </div>

    <section
      v-if="jornada.siguiente"
      aria-labelledby="titulo-siguiente"
      class="animate-aparecer rounded-[16px] border bg-white p-5 sm:p-6"
      :class="jornada.siguiente.pedido ? 'border-aviso/60' : 'border-borde'"
    >
      <p
        class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-bold"
        :class="
          jornada.siguiente.pedido ? 'bg-aviso-fondo text-aviso' : 'bg-acento-suave text-acento'
        "
      >
        <BaseIcono :nombre="jornada.siguiente.pedido ? 'reloj' : 'calendario'" class="size-3.5" />
        {{
          jornada.siguiente.pedido
            ? `${primerNombre(jornada.gerente)} te pidió pagarla`
            : 'Tu siguiente pago'
        }}
      </p>
      <div class="mt-3 flex items-start gap-3">
        <InsigniaCategoria
          :icono="categoriaDe(jornada.siguiente.categoria_id)?.icono ?? 'etiqueta'"
          :color="categoriaDe(jornada.siguiente.categoria_id)?.color ?? 'ciruela'"
        />
        <div class="min-w-0 flex-1">
          <h2
            id="titulo-siguiente"
            class="text-[20px] leading-tight font-extrabold tracking-[-0.02em]"
          >
            {{ jornada.siguiente.concepto }}
          </h2>
          <p class="mt-1 text-[28px] font-extrabold tracking-[-0.03em]">
            {{ formatearSoles(jornada.siguiente.importe) }}
          </p>
        </div>
      </div>
      <p v-if="jornada.siguiente.pedido?.nota" class="mt-3 text-[14px]">
        «{{ jornada.siguiente.pedido.nota }}»
      </p>
      <p v-else class="mt-3 text-[13px] text-secundario">
        Págala por tu canal habitual y deja el comprobante para que
        {{ primerNombre(jornada.gerente) }} lo revise.
      </p>
      <dl class="mt-4 grid grid-cols-1 gap-2 text-[12px] sm:grid-cols-2">
        <div>
          <dt class="text-secundario">Vence</dt>
          <dd class="font-bold" :class="jornada.siguiente.vence_el < hoy ? 'text-error' : ''">
            {{ formatearFecha(jornada.siguiente.vence_el) }} ·
            {{ cuandoVence(jornada.siguiente.vence_el, hoy) }}
          </dd>
        </div>
        <div>
          <dt class="text-secundario">Se paga en</dt>
          <dd class="font-bold">{{ nombresLugares(jornada.siguiente.lugares_pago) }}</dd>
        </div>
      </dl>
      <RouterLink
        :to="{
          name: 'registrar-pago',
          query: { deuda: jornada.siguiente.deuda_id, cuota: jornada.siguiente.cuota },
        }"
        class="mt-5 inline-flex min-h-11 items-center gap-2 rounded-[9px] bg-acento px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover"
      >
        Ya pagué · subir comprobante
        <BaseIcono nombre="derecha" class="size-4" />
      </RouterLink>
    </section>

    <section
      v-else
      class="flex flex-col items-center rounded-[16px] border border-dashed border-borde bg-white px-6 py-10 text-center"
    >
      <span
        aria-hidden="true"
        class="grid size-14 place-items-center rounded-[16px] bg-exito-fondo text-exito motion-safe:animate-flotar"
      >
        <BaseIcono nombre="check" class="size-6" />
      </span>
      <p class="mt-4 text-[18px] font-extrabold">Tu mesa está despejada.</p>
      <p class="mt-1 max-w-[44ch] text-[13px] text-secundario">
        No falta pagar ninguna cuota. Si llega un recibo, regístralo.
      </p>
    </section>

    <section class="flex items-start gap-3 rounded-[14px] bg-fondo p-4 text-[13px]">
      <BaseIcono nombre="escudo" class="mt-0.5 size-5 shrink-0 text-acento" />
      <p>
        <strong>La aprobación corresponde a {{ primerNombre(jornada.gerente) }}.</strong>
        <template v-if="jornada.limite">
          Si una deuda supera {{ formatearSoles(jornada.limite) }} o tiene otro titular, puedes
          registrarla; se pagará cuando la autorice.
        </template>
        <template v-else>
          Si una deuda tiene otro titular, puedes registrarla; se pagará cuando la autorice.
        </template>
      </p>
    </section>
  </div>
</template>
