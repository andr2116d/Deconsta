<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { RouterLink, useRoute, type RouteLocationRaw } from 'vue-router'

import type { Usuario } from '@/features/acceso/types'
import BaseAvatar from '@/shared/components/BaseAvatar.vue'
import BaseIcono from '@/shared/components/BaseIcono.vue'
import type { NombreIcono } from '@/shared/components/iconos'

import { seccionesDe, textoPorRol } from '../secciones'

// Tarjeta de la cuenta que se despliega desde el avatar. Sigue el patrón de botón que muestra y
// oculta (no el de menú de aplicación): se recorre con Tab y se cierra con Escape, al hacer clic
// fuera, al sacar el foco o al navegar.
const props = defineProps<{ usuario: Usuario; contrasenaTemporal: boolean; saliendo: boolean }>()
const emit = defineEmits<{ 'cambiar-contrasena': []; salir: [] }>()

const route = useRoute()
const abierto = ref(false)
const raiz = ref<HTMLElement>()
const disparador = ref<HTMLButtonElement>()
const idPanel = useId()

const rol = computed(() => (props.usuario.rol === 'gerente' ? 'Gerente' : 'Asistente'))

interface Opcion {
  clave: string
  etiqueta: string
  icono: NombreIcono
  destino: RouteLocationRaw
  temporal?: boolean
}

// Mientras la contraseña siga siendo temporal, «Usuario y contraseña» lo señala.
const opciones = computed<Opcion[]>(() =>
  seccionesDe(props.usuario.rol, 'cuenta').map((s) => ({
    clave: s.nombre,
    etiqueta: textoPorRol(s.etiqueta, props.usuario.rol),
    icono: s.icono,
    destino: { name: s.nombre },
    temporal: s.nombre === 'acceso-cuenta' && props.contrasenaTemporal,
  })),
)

function alternar() {
  abierto.value = !abierto.value
}

function cerrar(devolverFoco = false) {
  if (!abierto.value) return
  abierto.value = false
  if (devolverFoco) disparador.value?.focus()
}

function alPresionarFuera(evento: PointerEvent) {
  if (!raiz.value?.contains(evento.target as Node)) cerrar()
}

function alSacarFoco(evento: FocusEvent) {
  const destino = evento.relatedTarget as Node | null
  if (destino && !raiz.value?.contains(destino)) cerrar()
}

function cambiarContrasena() {
  cerrar()
  emit('cambiar-contrasena')
}

watch(abierto, (valor) => {
  if (valor) document.addEventListener('pointerdown', alPresionarFuera)
  else document.removeEventListener('pointerdown', alPresionarFuera)
})
watch(
  () => route.fullPath,
  () => cerrar(),
)
onBeforeUnmount(() => document.removeEventListener('pointerdown', alPresionarFuera))
</script>

<template>
  <div
    ref="raiz"
    class="relative"
    :data-menu-abierto="abierto || undefined"
    @keydown.esc="cerrar(true)"
    @focusout="alSacarFoco"
  >
    <button
      ref="disparador"
      type="button"
      :aria-expanded="abierto"
      :aria-controls="idPanel"
      class="flex items-center gap-2.5 rounded-xl p-1 text-left transition-colors duration-200 hover:bg-fondo md:pr-2"
      :class="abierto ? 'bg-fondo' : ''"
      @click="alternar"
    >
      <span class="relative">
        <BaseAvatar :nombre="usuario.nombres" />
        <span
          v-if="contrasenaTemporal"
          aria-hidden="true"
          class="absolute -top-0.5 -right-0.5 size-3 rounded-full border-2 border-white bg-aviso"
        />
      </span>
      <span class="sr-only">Tu cuenta</span>
      <span class="hidden max-w-[160px] leading-tight md:block">
        <strong class="block truncate text-[13px] font-bold">{{ usuario.nombres }}</strong>
        <small class="text-[11px] text-secundario">{{ rol }}</small>
      </span>
      <span v-if="contrasenaTemporal" class="sr-only">(tu contraseña sigue siendo temporal)</span>
      <BaseIcono
        nombre="abajo"
        class="hidden size-3.5 text-secundario transition-transform duration-200 sm:block"
        :class="abierto ? 'rotate-180' : ''"
      />
    </button>

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-1 scale-[0.98]"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0 -translate-y-1 scale-[0.98]"
    >
      <div
        v-if="abierto"
        :id="idPanel"
        class="absolute top-full right-0 z-40 mt-2 w-[min(320px,calc(100vw-32px))] origin-top-right rounded-[14px] border border-borde bg-white p-2 shadow-[0_20px_70px_#30233026]"
      >
        <div class="flex items-center gap-3 rounded-[10px] bg-fondo p-3">
          <BaseAvatar :nombre="usuario.nombres" tamano="grande" />
          <div class="min-w-0 flex-1 leading-tight">
            <p class="truncate text-[15px] font-extrabold">{{ usuario.nombres }}</p>
            <p class="mt-1 truncate text-[12px] text-secundario">@{{ usuario.nombre_usuario }}</p>
          </div>
          <span
            class="shrink-0 rounded-full bg-acento px-2.5 py-0.5 text-[11px] font-bold text-white"
          >
            {{ rol }}
          </span>
        </div>

        <button
          v-if="contrasenaTemporal"
          type="button"
          class="mt-2 flex w-full items-start gap-3 rounded-[10px] bg-aviso-fondo p-3 text-left text-aviso transition-colors duration-200 hover:bg-[#ffeac0]"
          @click="cambiarContrasena"
        >
          <BaseIcono nombre="candado" class="mt-0.5 size-[18px]" />
          <span class="leading-snug">
            <strong class="block text-[13px]">Tu contraseña sigue siendo temporal.</strong>
            <span class="text-[12px]">Cámbiala ahora para proteger tu cuenta.</span>
          </span>
        </button>

        <ul class="mt-1">
          <li v-for="opcion in opciones" :key="opcion.clave">
            <RouterLink
              :to="opcion.destino"
              class="flex min-h-11 items-center gap-3 rounded-lg px-3 text-[13px] transition-colors duration-200 hover:bg-fondo"
              active-class="font-bold text-acento"
            >
              <BaseIcono :nombre="opcion.icono" class="size-[18px] text-secundario" />
              <span class="flex-1">{{ opcion.etiqueta }}</span>
              <span
                v-if="opcion.temporal"
                class="rounded-full bg-aviso-fondo px-2 py-0.5 text-[11px] font-bold text-aviso"
              >
                Temporal
              </span>
            </RouterLink>
          </li>
        </ul>

        <div class="my-1 h-px bg-borde" />
        <button
          type="button"
          class="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-[13px] transition-colors duration-200 hover:bg-fondo disabled:opacity-70"
          :disabled="saliendo"
          :aria-busy="saliendo"
          @click="emit('salir')"
        >
          <BaseIcono nombre="salir" class="size-[18px] text-secundario" />
          {{ saliendo ? 'Cerrando sesión…' : 'Cerrar sesión' }}
        </button>
      </div>
    </Transition>
  </div>
</template>
