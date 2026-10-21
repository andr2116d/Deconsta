<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { obtenerDocumentos } from '@/features/incorporacion/api/incorporacion'
import LectorDocumento from '@/features/incorporacion/components/LectorDocumento.vue'
import type { DocumentoLegal } from '@/features/incorporacion/types'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import TarjetaCuenta from '../components/TarjetaCuenta.vue'
import { formatearFecha } from '../datos'

// Constancia de lo que la cuenta aceptó: la versión vigente de cada documento y su fecha.
const documentos = ref<DocumentoLegal[] | null>(null)
const error = ref<string | null>(null)
const abierto = ref<DocumentoLegal | null>(null)
const cargando = ref(false)

async function cargar() {
  cargando.value = true
  error.value = null
  try {
    documentos.value = await obtenerDocumentos()
  } catch (fallo) {
    error.value =
      fallo instanceof ErrorApi ? fallo.message : 'No pudimos cargar los documentos aceptados.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <TarjetaCuenta
    titulo="Privacidad y autorizaciones"
    descripcion="Los documentos que aceptaste para usar Deconsta. Si publicamos una versión nueva, te pediremos aceptarla al ingresar."
    :cargando="documentos === null && !error"
  >
    <div v-if="error" class="flex flex-col items-start gap-3">
      <BaseAviso tono="error" class="w-full">{{ error }}</BaseAviso>
      <BaseBoton variante="secundario" :cargando="cargando" @click="cargar">Reintentar</BaseBoton>
    </div>
    <ul v-else-if="documentos" class="flex flex-col gap-3">
      <li
        v-for="documento in documentos"
        :key="documento.tipo"
        class="flex flex-col gap-3 rounded-[10px] border border-borde p-4 sm:flex-row sm:items-center"
      >
        <span
          aria-hidden="true"
          class="grid size-10 shrink-0 place-items-center rounded-[10px] bg-acento-suave text-acento"
        >
          <BaseIcono nombre="documento" class="size-5" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-[14px] font-bold">{{ documento.titulo }}</p>
          <p class="text-[12px] text-secundario">{{ documento.resumen }}</p>
          <p
            class="mt-1 text-[12px] font-bold"
            :class="documento.aceptado_en ? 'text-exito' : 'text-aviso'"
          >
            Versión {{ documento.version }} ·
            {{
              documento.aceptado_en
                ? `aceptada el ${formatearFecha(documento.aceptado_en)}`
                : 'pendiente de aceptar'
            }}
          </p>
        </div>
        <BaseBoton variante="secundario" @click="abierto = documento">Leer</BaseBoton>
      </li>
    </ul>
    <p class="mt-5 text-[12px] text-secundario">
      Conforme a la Ley N.° 29733, puedes solicitar el acceso, la rectificación, la cancelación o la
      oposición al tratamiento de tus datos personales.
    </p>
    <LectorDocumento :documento="abierto" @cerrar="abierto = null" />
  </TarjetaCuenta>
</template>
