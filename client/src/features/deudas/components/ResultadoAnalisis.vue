<script setup lang="ts">
import { computed } from 'vue'

import BaseIcono from '@/shared/components/BaseIcono.vue'

import type { Capa, Documento, Riesgo } from '../types'

/**
 * Lo que se comprobó del documento, capa por capa. Cada fila dice qué se vio; la decisión la
 * toma el backend con las mismas señales.
 */
const props = defineProps<{ documento: Documento | null; revisando: boolean }>()

type Estado = 'pendiente' | 'bien' | 'duda' | 'mal'

const CAPAS: { capa: Capa | 'repetido'; titulo: string; bien: string }[] = [
  { capa: 'lectura', titulo: 'Lectura del documento', bien: 'El texto se lee completo.' },
  {
    capa: 'ia',
    titulo: 'Revisión del contenido',
    bien: 'Los datos son coherentes con un documento de su emisor.',
  },
  {
    capa: 'metadatos',
    titulo: 'Archivo original',
    bien: 'No muestra señales de haberse editado.',
  },
  {
    capa: 'repetido',
    titulo: 'Documento sin reutilizar',
    bien: 'No respalda otra deuda de tu espacio.',
  },
]

const RANGO: Riesgo[] = ['bajo', 'medio', 'alto']
const NIVEL: Record<Riesgo, Estado> = { bajo: 'bien', medio: 'duda', alto: 'mal' }
const ICONOS: Record<Estado, 'reloj' | 'check' | 'alerta' | 'cerrar'> = {
  pendiente: 'reloj',
  bien: 'check',
  duda: 'alerta',
  mal: 'cerrar',
}
const ESTILOS: Record<Estado, string> = {
  pendiente: 'bg-fondo text-secundario',
  bien: 'bg-exito-fondo text-exito',
  duda: 'bg-aviso-fondo text-aviso',
  mal: 'bg-error-fondo text-error',
}

const filas = computed(() => {
  const documento = props.documento
  const terminado = documento && documento.estado !== 'analizando' && !props.revisando
  return CAPAS.map(({ capa, titulo, bien }) => {
    if (!terminado || !documento) {
      return { capa, titulo, estado: 'pendiente' as Estado, detalle: 'Pendiente de revisar.' }
    }
    if (capa === 'repetido') {
      const repetido = documento.estado === 'repetido'
      return {
        capa,
        titulo,
        estado: (repetido
          ? 'mal'
          : documento.estado === 'ilegible'
            ? 'pendiente'
            : 'bien') as Estado,
        detalle: repetido
          ? `Ya respalda «${documento.repetido_de?.concepto ?? 'otra deuda'}».`
          : documento.estado === 'ilegible'
            ? 'No se pudo comprobar sin leer el documento.'
            : bien,
      }
    }
    const senales = documento.senales.filter((s) => s.capa === capa)
    if (capa === 'ia' && documento.estado === 'ilegible' && !senales.length) {
      return { capa, titulo, estado: 'pendiente' as Estado, detalle: 'No se revisó: no se lee.' }
    }
    const peor = senales.reduce<Riesgo>(
      (actual, s) => (RANGO.indexOf(s.riesgo) > RANGO.indexOf(actual) ? s.riesgo : actual),
      'bajo',
    )
    return {
      capa,
      titulo,
      estado: NIVEL[peor],
      detalle: senales.length ? senales.map((s) => s.detalle).join(' ') : bien,
    }
  })
})
</script>

<template>
  <section aria-labelledby="titulo-comprobaciones">
    <h2 id="titulo-comprobaciones" class="text-[14px] font-extrabold">Lo que comprobamos</h2>
    <p class="mt-1 mb-2 text-[12px] text-secundario">
      Una ayuda para registrar sin errores. Revisa igual el documento.
    </p>
    <ul>
      <li
        v-for="fila in filas"
        :key="fila.capa"
        class="flex items-start gap-3 border-b border-borde py-3 last:border-b-0"
      >
        <span
          aria-hidden="true"
          class="mt-0.5 grid size-[26px] shrink-0 place-items-center rounded-full transition-colors duration-300"
          :class="ESTILOS[fila.estado]"
        >
          <BaseIcono :nombre="ICONOS[fila.estado]" class="size-3.5" />
        </span>
        <div class="min-w-0">
          <strong class="block text-[13px]">{{ fila.titulo }}</strong>
          <small class="block text-[12px] leading-snug text-secundario">{{ fila.detalle }}</small>
        </div>
        <span class="sr-only">
          {{
            {
              pendiente: 'Pendiente',
              bien: 'Correcto',
              duda: 'Por revisar',
              mal: 'No cumple',
            }[fila.estado]
          }}
        </span>
      </li>
    </ul>
  </section>
</template>
