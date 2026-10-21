<script setup lang="ts">
import { computed } from 'vue'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import type { Rol } from '@/features/acceso/types'
import BaseAvatar from '@/shared/components/BaseAvatar.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'

import TarjetaCuenta from '../components/TarjetaCuenta.vue'

// Informativo: resume qué le corresponde a cada rol. La autorización real la decide el backend en
// cada operación.
const sesion = useSesionStore()

const PERMISOS: ReadonlyArray<{ accion: string; gerente: boolean; asistente: boolean }> = [
  { accion: 'Registrar deudas', gerente: true, asistente: true },
  { accion: 'Adjuntar comprobantes de pago', gerente: false, asistente: true },
  { accion: 'Autorizar importes altos', gerente: true, asistente: false },
  { accion: 'Aprobar recibos de otro titular', gerente: true, asistente: false },
  { accion: 'Dar prioridad a un pago', gerente: true, asistente: false },
  { accion: 'Verificar o devolver comprobantes', gerente: true, asistente: false },
  { accion: 'Crear cuentas de asistentes', gerente: true, asistente: false },
  { accion: 'Configurar límites y categorías', gerente: true, asistente: false },
  { accion: 'Actualizar mis datos personales', gerente: true, asistente: true },
]

const ROLES: ReadonlyArray<{ rol: Rol; nombre: string }> = [
  { rol: 'gerente', nombre: 'Gerente' },
  { rol: 'asistente', nombre: 'Asistente' },
]

const rol = computed(() => sesion.usuario?.rol ?? 'asistente')
const responsabilidad = computed(() =>
  rol.value === 'gerente'
    ? 'Tu responsabilidad es autorizar, asignar y verificar.'
    : 'Tu responsabilidad es registrar, ejecutar y corregir.',
)
</script>

<template>
  <TarjetaCuenta titulo="Mi rol y permisos">
    <div class="mt-4 mb-6 flex flex-wrap items-center gap-3">
      <BaseAvatar :nombre="sesion.usuario?.nombres ?? ''" />
      <div class="min-w-0 flex-1">
        <p class="text-[15px] font-extrabold">
          {{ rol === 'gerente' ? 'Gerente' : 'Asistente' }}
        </p>
        <p class="text-[12px] text-secundario">{{ responsabilidad }}</p>
      </div>
      <span
        class="inline-flex items-center gap-1.5 rounded-md bg-acento-suave px-2 py-1 text-[11px] font-bold text-acento"
      >
        <span aria-hidden="true" class="size-1.5 rounded-full bg-current" />
        Rol asignado
      </span>
    </div>

    <table class="w-full table-fixed border-collapse text-left text-[13px]">
      <caption class="sr-only">
        Qué puede hacer cada rol
      </caption>
      <colgroup>
        <col />
        <col class="w-[72px] sm:w-[96px]" />
        <col class="w-[72px] sm:w-[96px]" />
      </colgroup>
      <thead>
        <tr class="border-b border-borde text-[11px] text-secundario">
          <th scope="col" class="py-2.5 font-semibold">Acción</th>
          <th
            v-for="columna in ROLES"
            :key="columna.rol"
            scope="col"
            class="py-2.5 text-center font-semibold"
            :class="columna.rol === rol ? 'font-extrabold text-acento' : ''"
          >
            {{ columna.nombre }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="permiso in PERMISOS" :key="permiso.accion" class="border-b border-borde">
          <th scope="row" class="py-3 pr-2 font-normal">{{ permiso.accion }}</th>
          <td
            v-for="columna in ROLES"
            :key="columna.rol"
            class="py-3 text-center"
            :class="columna.rol === rol ? 'bg-acento-suave/40' : ''"
          >
            <BaseIcono
              :nombre="permiso[columna.rol] ? 'check' : 'cerrar'"
              class="mx-auto size-4"
              :class="permiso[columna.rol] ? 'text-exito' : 'text-control'"
            />
            <span class="sr-only">{{ permiso[columna.rol] ? 'Permitido' : 'No permitido' }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="mt-5 text-[12px] text-secundario">
      Tu rol lo define quien creó tu cuenta y no se cambia desde Mi cuenta. Deconsta comprueba tu
      permiso en cada acción.
    </p>
  </TarjetaCuenta>
</template>
