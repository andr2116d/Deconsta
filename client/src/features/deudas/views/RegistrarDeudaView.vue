<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import { useCategoriasStore } from '@/features/categorias/stores/categorias'
import BaseAviso from '@/shared/components/BaseAviso.vue'
import BaseBoton from '@/shared/components/BaseBoton.vue'

import ConfirmacionRegistro from '../components/ConfirmacionRegistro.vue'
import DialogoDocumentoRepetido from '../components/DialogoDocumentoRepetido.vue'
import FormularioDeuda from '../components/FormularioDeuda.vue'
import ResultadoAnalisis from '../components/ResultadoAnalisis.vue'
import ZonaDocumento from '../components/ZonaDocumento.vue'
import { useAnalisisDocumento } from '../composables/useAnalisisDocumento'
import type { DeudaExistente, RegistroDeuda } from '../types'

const router = useRouter()
const sesion = useSesionStore()
const categorias = useCategoriasStore()
const { etapa, documento, archivo, vistaPrevia, error, demorado, cargar, reiniciar } =
  useAnalisisDocumento()

const rol = computed(() => sesion.usuario?.rol ?? 'asistente')
const registro = ref<RegistroDeuda | null>(null)
const repetido = ref<{ deuda: DeudaExistente; bloqueado: boolean } | null>(null)
const bloqueado = ref(false)

const paso = computed(() => {
  if (registro.value) return 3
  return etapa.value === 'vacio' || etapa.value === 'error' ? 1 : 2
})
const PASOS = ['Documento', 'Revisión', 'Registro'] as const
const revisando = computed(() => etapa.value === 'subiendo' || etapa.value === 'analizando')
const estado = computed(() => (etapa.value === 'terminado' ? documento.value?.estado : null))

function sesionTerminada() {
  sesion.olvidar()
  router.replace({ name: 'inicio-sesion' })
}

watch(error, (actual) => {
  if (!actual) return
  if (actual.codigo === 'NO_AUTENTICADO') sesionTerminada()
  if (actual.codigo === 'REGISTRO_DEUDAS_BLOQUEADO') bloqueado.value = true
  if (actual.codigo === 'DOCUMENTO_YA_REGISTRADO') {
    const existente = actual.cuerpo.existing_debt as DeudaExistente | undefined
    const conBloqueo = actual.cuerpo.registration_blocked === true
    if (existente) repetido.value = { deuda: existente, bloqueado: conBloqueo }
    bloqueado.value = conBloqueo
  }
})
watch(estado, (actual) => {
  const anterior = documento.value?.repetido_de
  if (actual === 'repetido' && anterior) repetido.value = { deuda: anterior, bloqueado: false }
})

async function alRegistrar(nuevo: RegistroDeuda) {
  registro.value = nuevo
  await nextTick()
  document.getElementById('titulo-seccion')?.focus()
}

function otraDeuda() {
  registro.value = null
  repetido.value = null
  reiniciar()
}

function otroDocumento() {
  repetido.value = null
  reiniciar()
}

onMounted(() => {
  // Las categorías del espacio de esta sesión, nunca las de una anterior.
  categorias.olvidar()
  categorias.cargar().catch(() => undefined)
})
</script>

<template>
  <ConfirmacionRegistro v-if="registro" :registro="registro" :rol="rol" @otra="otraDeuda" />

  <section v-else aria-labelledby="titulo-seccion">
    <h1
      id="titulo-seccion"
      tabindex="-1"
      class="text-[26px] leading-tight font-extrabold tracking-[-0.03em] focus:outline-none sm:text-[32px]"
    >
      Del documento a tu agenda.
    </h1>
    <p class="mt-2 mb-6 max-w-[62ch] text-[13px] text-secundario sm:mb-8">
      Sube el recibo, la boleta o el cronograma. Lo leemos, revisamos que sea original y llenamos
      los datos por ti; tú los confirmas.
    </p>

    <BaseAviso
      v-if="bloqueado && !repetido"
      tono="error"
      class="mb-6"
      titulo="Tu registro de deudas está en pausa"
    >
      Intentaste varias veces usar documentos que ya respaldan otras deudas. Tu gerente ya lo sabe y
      puede permitirte registrar otra vez desde Mi equipo. Mientras tanto, puedes seguir con tus
      demás tareas.
    </BaseAviso>

    <div class="grid items-start gap-6 lg:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.1fr)] lg:gap-8">
      <ZonaDocumento
        :etapa="etapa"
        :archivo="archivo"
        :vista-previa="vistaPrevia"
        :demorado="demorado"
        @elegir="cargar"
        @cambiar="otroDocumento"
      />

      <div class="rounded-[14px] border border-borde bg-white p-5 sm:p-7">
        <ol class="mb-6 flex items-center gap-2.5 text-[11px] text-secundario" aria-label="Pasos">
          <template v-for="(nombre, indice) in PASOS" :key="nombre">
            <li
              class="inline-flex items-center gap-1.5 transition-colors duration-300"
              :class="indice + 1 <= paso ? 'font-bold text-acento' : ''"
              :aria-current="indice + 1 === paso ? 'step' : undefined"
            >
              <b
                class="inline-grid size-5 place-items-center rounded-full text-[10px] transition-colors duration-300"
                :class="indice + 1 <= paso ? 'bg-acento text-white' : 'bg-borde'"
              >
                {{ indice + 1 }}
              </b>
              {{ nombre }}
            </li>
            <li v-if="indice < PASOS.length - 1" aria-hidden="true" class="h-px flex-1 bg-borde" />
          </template>
        </ol>

        <Transition name="vista" mode="out-in">
          <div v-if="etapa === 'vacio'" key="vacio">
            <ResultadoAnalisis :documento="null" :revisando="false" />
            <p class="mt-4 text-[12px] text-secundario">
              Si el documento no se lee, no se puede registrar: sin leerlo no hay forma de comprobar
              a qué gasto corresponde.
            </p>
          </div>

          <div v-else-if="etapa === 'error' && error" key="error">
            <BaseAviso tono="error" titulo="No pudimos usar este documento">
              {{ error.message }}
            </BaseAviso>
            <BaseBoton v-if="!bloqueado" class="mt-4" @click="otroDocumento">
              Elegir otro documento
            </BaseBoton>
          </div>

          <div v-else key="analisis">
            <ResultadoAnalisis :documento="documento" :revisando="revisando" />

            <div v-if="estado === 'listo' && documento" class="mt-6 border-t border-borde pt-6">
              <BaseAviso
                v-if="documento.riesgo === 'medio' && rol === 'asistente'"
                tono="aviso"
                class="mb-5"
                titulo="Esperará la autorización de tu gerente"
              >
                El documento tiene señales que conviene revisar. Puedes registrar la deuda; tu
                gerente recibirá un aviso en tiempo real y decidirá antes de que se pague.
              </BaseAviso>
              <BaseAviso
                v-else-if="documento.riesgo !== 'bajo' && rol === 'gerente'"
                tono="aviso"
                class="mb-5"
                titulo="Revisa el documento antes de registrarlo"
              >
                Encontramos señales que conviene mirar. Como es tu espacio, puedes registrarla
                igual.
              </BaseAviso>
              <FormularioDeuda
                :documento="documento"
                :rol="rol"
                @registrada="alRegistrar"
                @sesion-terminada="sesionTerminada"
              />
            </div>

            <div v-else-if="estado === 'ilegible'" class="mt-6">
              <BaseAviso tono="error" titulo="No se puede leer el documento">
                Sin leerlo no podemos comprobar a qué gasto corresponde, así que no se puede
                registrar. Sube una foto nítida, completa y con buena luz, o el PDF original.
              </BaseAviso>
              <BaseBoton class="mt-4" @click="otroDocumento">Subir otro documento</BaseBoton>
            </div>

            <div v-else-if="estado === 'rechazado'" class="mt-6">
              <BaseAviso tono="error" titulo="El documento parece alterado">
                No puede respaldar una deuda. Sube el documento original que entregó el emisor. Si
                crees que es un error, coméntalo con tu gerente.
              </BaseAviso>
              <BaseBoton class="mt-4" @click="otroDocumento">Subir otro documento</BaseBoton>
            </div>

            <div v-else-if="estado === 'no_es_deuda'" class="mt-6">
              <BaseAviso tono="error" titulo="Este documento no cobra una deuda">
                Parece el comprobante de un pago ya hecho u otro documento que no cobra nada. Sube
                el recibo, la boleta o el documento que cobra lo que se debe.
              </BaseAviso>
              <BaseBoton class="mt-4" @click="otroDocumento">Subir otro documento</BaseBoton>
            </div>

            <div v-else-if="estado === 'repetido'" class="mt-6">
              <BaseAviso tono="error" titulo="Este documento ya respalda otra deuda">
                Cada documento se usa una sola vez. Sube el de la deuda que quieres registrar.
              </BaseAviso>
              <BaseBoton class="mt-4" @click="otroDocumento">Subir otro documento</BaseBoton>
            </div>

            <div v-else-if="estado === 'fallido'" class="mt-6">
              <BaseAviso tono="error" titulo="No terminamos de revisar el documento">
                Fue un problema nuestro, no de tu documento. Vuelve a subirlo en unos minutos.
              </BaseAviso>
              <BaseBoton class="mt-4" @click="otroDocumento">Subirlo otra vez</BaseBoton>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <DialogoDocumentoRepetido
      :deuda="repetido?.deuda ?? null"
      :bloqueado="repetido?.bloqueado ?? false"
      @cerrar="repetido = null"
      @otro="otroDocumento"
    />
  </section>
</template>
