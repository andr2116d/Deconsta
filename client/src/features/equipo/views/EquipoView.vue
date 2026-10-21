<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { levantarBloqueo, listarBloqueos } from '@/features/deudas/api/deudas'
import type { BloqueoRegistro } from '@/features/deudas/types'
import { levantarBloqueoPagos, listarBloqueosPagos } from '@/features/pagos/api/pagos'
import type { BloqueoPagos } from '@/features/pagos/types'
import { ErrorApi } from '@/shared/api/http'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import DialogoFalloGuardado from '@/shared/components/DialogoFalloGuardado.vue'

import DialogoAccionAsistente from '../components/DialogoAccionAsistente.vue'
import DialogoCredenciales from '../components/DialogoCredenciales.vue'
import TarjetaAsistente from '../components/TarjetaAsistente.vue'
import { useEquipoStore } from '../stores/equipo'
import type { AccionAsistente, Asistente, Credenciales } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const equipo = useEquipoStore()

const accion = ref<{ tipo: AccionAsistente; asistente: Asistente } | null>(null)
// La contraseña restablecida se muestra una sola vez, para copiarla y entregarla.
const restablecidas = ref<Credenciales | null>(null)
const ocupada = ref<string | null>(null)
const aviso = ref<string | null>(
  typeof history.state?.aviso === 'string' ? (history.state.aviso as string) : null,
)
const fallo = ref<ErrorApi | null>(null)
const bloqueos = ref<BloqueoRegistro[]>([])
const bloqueoDe = (a: Asistente) =>
  bloqueos.value.find((b) => b.asistente_id === a.id)?.bloqueado_en ?? null
const bloqueosPagos = ref<BloqueoPagos[]>([])
const pagosBloqueadosDe = (a: Asistente) =>
  bloqueosPagos.value.find((b) => b.asistente_id === a.id)?.bloqueado_en ?? null

const cantidad = computed(() => equipo.asistentes?.length ?? 0)
const nombreDe = (a: Asistente) => `${a.nombres} ${a.apellidos}`

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

function mostrarFallo(error: unknown) {
  if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') {
    sesionTerminada()
    return
  }
  fallo.value =
    error instanceof ErrorApi
      ? error
      : new ErrorApi(0, { code: 'ERROR_INTERNO', detail: 'Ocurrió un error inesperado.' })
}

async function cargar() {
  try {
    await equipo.cargar()
    const [deDeudas, dePagos] = await Promise.all([listarBloqueos(), listarBloqueosPagos()])
    bloqueos.value = deDeudas
    bloqueosPagos.value = dePagos
  } catch (error) {
    if (error instanceof ErrorApi && error.codigo === 'NO_AUTENTICADO') sesionTerminada()
  }
}

async function confirmarAccion(motivo: string | null) {
  if (!accion.value) return
  const { tipo, asistente } = accion.value
  ocupada.value = asistente.id
  aviso.value = null
  try {
    if (tipo === 'bloquear') {
      await equipo.bloquear(asistente.id, motivo)
      aviso.value = `Bloqueaste a ${nombreDe(asistente)}. Sus sesiones abiertas se cerraron.`
    } else if (tipo === 'restablecer') {
      restablecidas.value = await equipo.restablecer(asistente.id, motivo)
    } else {
      await equipo.eliminar(asistente.id, motivo)
      aviso.value = `Eliminaste la cuenta de ${nombreDe(asistente)}. Puedes recuperarla si vuelve.`
    }
    accion.value = null
  } catch (error) {
    accion.value = null
    mostrarFallo(error)
  } finally {
    ocupada.value = null
  }
}

function cerrarRestablecidas() {
  if (restablecidas.value) {
    const asistente = restablecidas.value.asistente
    aviso.value = `Restableciste la contraseña de ${nombreDe(asistente)}. Sus sesiones abiertas se cerraron.`
  }
  restablecidas.value = null
}

async function desbloquear(asistente: Asistente) {
  ocupada.value = asistente.id
  aviso.value = null
  try {
    await equipo.desbloquear(asistente.id)
    aviso.value = `Desbloqueaste a ${nombreDe(asistente)}. Ya puede volver a ingresar.`
  } catch (error) {
    mostrarFallo(error)
  } finally {
    ocupada.value = null
  }
}

async function permitirRegistro(asistente: Asistente) {
  ocupada.value = asistente.id
  aviso.value = null
  try {
    await levantarBloqueo(asistente.id)
    bloqueos.value = bloqueos.value.filter((b) => b.asistente_id !== asistente.id)
    aviso.value = `${nombreDe(asistente)} ya puede registrar deudas otra vez. Le avisamos.`
  } catch (error) {
    mostrarFallo(error)
  } finally {
    ocupada.value = null
  }
}

async function permitirPagos(asistente: Asistente) {
  ocupada.value = asistente.id
  aviso.value = null
  try {
    await levantarBloqueoPagos(asistente.id)
    bloqueosPagos.value = bloqueosPagos.value.filter((b) => b.asistente_id !== asistente.id)
    aviso.value = `${nombreDe(asistente)} ya puede registrar pagos otra vez. Le avisamos.`
  } catch (error) {
    mostrarFallo(error)
  } finally {
    ocupada.value = null
  }
}

onMounted(() => {
  // Nunca se ven, ni por un instante, las asistentes de otra sesión.
  equipo.olvidar()
  void cargar()
})
</script>

<template>
  <section aria-labelledby="titulo-seccion">
    <header class="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          id="titulo-seccion"
          tabindex="-1"
          class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
        >
          Tu equipo comienza contigo.
        </h1>
        <p class="mt-2 text-[13px] text-secundario">
          Registra a las personas que prepararán las deudas y completarán los pagos.
        </p>
      </div>
      <RouterLink
        :to="{ name: 'registrar-asistente' }"
        class="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 self-start rounded-[9px] bg-acento px-4 text-[13px] font-bold text-white transition-colors duration-200 hover:bg-acento-hover sm:self-auto"
      >
        <BaseIcono nombre="mas" class="size-[18px]" />
        Registrar asistente
      </RouterLink>
    </header>

    <BaseAviso v-if="aviso" tono="exito" class="mb-6">{{ aviso }}</BaseAviso>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-8">
      <div class="min-w-0">
        <div class="mb-4 flex items-center gap-3 rounded-[14px] bg-acento-suave p-4">
          <span
            aria-hidden="true"
            class="grid size-11 place-items-center rounded-full bg-white font-extrabold text-acento"
          >
            {{ sesion.usuario?.nombres.slice(0, 1).toUpperCase() }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-[15px] font-extrabold">{{ sesion.usuario?.nombres }}</p>
            <p class="text-[12px] text-secundario">Gerente · administra este espacio</p>
          </div>
          <BaseIcono nombre="escudo" class="size-5 text-acento" />
        </div>
        <p class="mb-4 text-[13px] text-secundario" aria-live="polite">
          <template v-if="equipo.asistentes">
            {{ cantidad === 1 ? '1 asistente' : `${cantidad} asistentes` }} en tu equipo
          </template>
        </p>

        <div v-if="equipo.errorCarga && !equipo.asistentes" class="flex flex-col items-start gap-3">
          <BaseAviso tono="error" titulo="No pudimos cargar tu equipo" class="w-full">
            {{
              equipo.errorCarga instanceof ErrorApi
                ? equipo.errorCarga.message
                : 'Ocurrió un error inesperado.'
            }}
          </BaseAviso>
          <BaseBoton variante="secundario" :cargando="equipo.cargando" @click="cargar">
            Reintentar
          </BaseBoton>
        </div>

        <div
          v-else-if="!equipo.asistentes"
          aria-hidden="true"
          class="flex flex-col gap-4 motion-safe:animate-pulse"
        >
          <div
            v-for="n in 2"
            :key="n"
            class="h-[220px] rounded-[14px] border border-borde bg-white"
          />
        </div>

        <div
          v-else-if="cantidad === 0"
          class="flex flex-col items-center rounded-[14px] border border-dashed border-borde bg-white px-6 py-12 text-center"
        >
          <span
            aria-hidden="true"
            class="grid size-14 place-items-center rounded-[16px] bg-acento-suave text-acento motion-safe:animate-flotar"
          >
            <BaseIcono nombre="equipo" class="size-6" />
          </span>
          <p class="mt-5 text-[18px] font-extrabold">Aún no registras asistentes.</p>
          <p class="mt-2 max-w-[44ch] text-[13px] text-secundario">
            Crea una cuenta para cada persona: así sabrás quién registró, pagó o corrigió cada
            documento.
          </p>
        </div>

        <TransitionGroup
          v-else
          tag="div"
          class="flex flex-col gap-4"
          leave-active-class="transition duration-200 ease-in"
          leave-to-class="opacity-0 -translate-x-2"
        >
          <TarjetaAsistente
            v-for="asistente in equipo.asistentes"
            :key="asistente.id"
            :asistente="asistente"
            :ocupada="ocupada === asistente.id"
            :registro-bloqueado="bloqueoDe(asistente)"
            :pagos-bloqueados="pagosBloqueadosDe(asistente)"
            @permitir-registro="permitirRegistro(asistente)"
            @permitir-pagos="permitirPagos(asistente)"
            @bloquear="accion = { tipo: 'bloquear', asistente }"
            @desbloquear="desbloquear(asistente)"
            @eliminar="accion = { tipo: 'eliminar', asistente }"
            @restablecer="accion = { tipo: 'restablecer', asistente }"
          />
        </TransitionGroup>
      </div>

      <aside class="flex flex-col gap-4 self-start">
        <div class="rounded-[14px] border border-borde bg-white p-5">
          <BaseIcono nombre="escudo" class="size-6 text-acento" />
          <h2 class="mt-3 text-[15px] font-extrabold">La decisión final sigue siendo tuya.</h2>
          <p class="mt-1.5 text-[13px] text-secundario">
            Una asistente no autoriza deudas, no cambia los límites ni verifica sus propios
            comprobantes.
          </p>
          <RouterLink
            :to="{ name: 'permisos' }"
            class="mt-3 inline-flex min-h-8 items-center gap-1 text-[12px] font-bold text-acento hover:underline"
          >
            Comparar permisos
            <BaseIcono nombre="derecha" class="size-3.5" />
          </RouterLink>
        </div>
        <div class="rounded-[14px] bg-fondo p-5 text-[13px] text-secundario">
          <h2 class="text-[15px] font-extrabold text-tinta">El trabajo es del equipo.</h2>
          <p class="mt-1.5">
            Todas tus asistentes ven lo mismo. Si eliminas a una, lo pendiente sigue disponible para
            las demás y para quien registres después.
          </p>
        </div>
      </aside>
    </div>

    <DialogoCredenciales
      :credenciales="restablecidas"
      motivo="restablecida"
      @cerrar="cerrarRestablecidas"
    />
    <DialogoAccionAsistente
      :accion="accion"
      :enviando="ocupada !== null"
      @confirmar="confirmarAccion"
      @cancelar="accion = null"
    />
    <DialogoFalloGuardado
      :error="fallo"
      titulo="No pudimos completar la acción"
      :etiquetas="{}"
      @cerrar="fallo = null"
      @reintentar="
        () => {
          fallo = null
          void cargar()
        }
      "
    />
  </section>
</template>
