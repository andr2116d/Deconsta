import { createRouter, createWebHistory } from 'vue-router'

import { useSesionStore } from '@/features/acceso/stores/sesion'

declare module 'vue-router' {
  interface RouteMeta {
    titulo: string
    requiereSesion?: boolean
    soloInvitados?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: { name: 'inicio' } },
    {
      path: '/ingresar',
      name: 'inicio-sesion',
      component: () => import('@/features/acceso/views/InicioSesionView.vue'),
      meta: { titulo: 'Inicia sesión', soloInvitados: true },
    },
    {
      path: '/cambiar-contrasena',
      name: 'cambio-contrasena',
      component: () => import('@/features/acceso/views/CambioContrasenaView.vue'),
      meta: { titulo: 'Cambia tu contraseña', requiereSesion: true },
    },
    {
      path: '/inicio',
      name: 'inicio',
      component: () => import('@/features/proximamente/views/ProximamenteView.vue'),
      meta: { titulo: 'Inicio', requiereSesion: true },
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
})

router.afterEach((destino) => {
  document.title = `${destino.meta.titulo} · Deconsta`
})

export default router
