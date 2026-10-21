import { createRouter, createWebHistory } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'
import type { Rol } from '@/features/acceso/types'
import { rutasDelEspacio, textoPorRol, type Seccion } from '@/features/espacio/secciones'

declare module 'vue-router' {
  interface RouteMeta {
    titulo: string
    requiereSesion?: boolean
    soloInvitados?: boolean
    /** Pantalla de los pasos del primer ingreso: solo mientras quede alguno pendiente. */
    incorporacion?: boolean
    /** Sección del espacio de trabajo que muestra la ruta. */
    seccion?: Seccion
    /** Roles que ven la ruta. Sin indicarlo, cualquier cuenta con sesión. */
    roles?: readonly Rol[]
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/ingresar',
      name: 'inicio-sesion',
      component: () => import('@/features/acceso/views/InicioSesionView.vue'),
      meta: { titulo: 'Inicia sesión', soloInvitados: true },
    },
    {
      path: '/bienvenida',
      name: 'incorporacion',
      component: () => import('@/features/incorporacion/views/IncorporacionView.vue'),
      meta: { titulo: 'Bienvenida', requiereSesion: true, incorporacion: true },
    },
    // El cambio de contraseña vive ahora en «Mi cuenta»; los enlaces anteriores siguen sirviendo.
    { path: '/cambiar-contrasena', redirect: { name: 'acceso-cuenta' } },
    {
      path: '/',
      component: () => import('@/features/espacio/layouts/EspacioLayout.vue'),
      meta: { titulo: 'Tu espacio', requiereSesion: true },
      children: [{ path: '', redirect: { name: 'inicio' } }, ...rutasDelEspacio()],
    },
    { path: '/:ruta(.*)*', redirect: { name: 'inicio' } },
  ],
})

// La guarda solo decide la navegación. Cada solicitud la vuelve a autorizar el backend.
router.beforeEach(async (destino) => {
  const sesion = useSesionStore()
  try {
    await sesion.comprobar()
  } catch {
    // Sin conexión con la API: se trata como sin sesión y el formulario mostrará el error.
  }
  if (destino.meta.requiereSesion && !sesion.autenticada) return { name: 'inicio-sesion' }
  if (destino.meta.soloInvitados && sesion.autenticada) return { name: 'inicio' }
  // Con un paso pendiente, cualquier otra pantalla de la sesión lleva a completarlo.
  const pendiente = sesion.pasosPendientes.length > 0
  if (sesion.autenticada && pendiente && !destino.meta.incorporacion) {
    return { name: 'incorporacion' }
  }
  if (destino.meta.incorporacion && !pendiente) return { name: 'inicio' }
  // Una sección de otro rol lleva al inicio propio (por ejemplo, un enlace compartido).
  const rol = sesion.usuario?.rol
  if (rol && destino.meta.roles && !destino.meta.roles.includes(rol)) return { name: 'inicio' }
})

router.afterEach((destino) => {
  // El inicio se llama distinto para cada rol (Resumen o Mi jornada).
  const rol = useSesionStore().usuario?.rol
  const { seccion, titulo } = destino.meta
  document.title = `${seccion && rol ? textoPorRol(seccion.etiqueta, rol) : titulo} · Deconsta`
})

export default router
