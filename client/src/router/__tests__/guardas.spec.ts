import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  respuesta,
  SESION,
  SESION_HABILITADA,
  simularFetch,
} from '@/features/acceso/__tests__/respuestas'

async function routerNuevo() {
  vi.resetModules()
  return (await import('../index')).default
}

describe('guardas de navegación', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('envía al ingreso a quien no tiene sesión', async () => {
    simularFetch(respuesta(401, { code: 'NO_AUTENTICADO', detail: 'Inicia sesión.' }))
    const router = await routerNuevo()

    await router.push('/inicio')

    expect(router.currentRoute.value.name).toBe('inicio-sesion')
  })

  it('no muestra el ingreso a quien ya tiene sesión', async () => {
    simularFetch(respuesta(200, SESION_HABILITADA))
    const router = await routerNuevo()

    await router.push('/ingresar')

    expect(router.currentRoute.value.name).toBe('inicio')
  })

  it('trata una API caída como sin sesión', async () => {
    simularFetch(Promise.reject(new TypeError('Failed to fetch')))
    const router = await routerNuevo()

    await router.push('/cambiar-contrasena')

    expect(router.currentRoute.value.name).toBe('inicio-sesion')
  })

  it.each(['/inicio', '/cambiar-contrasena', '/ingresar', '/otra-ruta'])(
    'retiene en la bienvenida a quien tiene un paso pendiente (%s)',
    async (ruta) => {
      simularFetch(respuesta(200, { ...SESION, pasos_pendientes: ['aceptar_documentos'] }))
      const router = await routerNuevo()

      await router.push(ruta)

      expect(router.currentRoute.value.name).toBe('incorporacion')
    },
  )

  it('saca de la bienvenida a quien ya completó los pasos', async () => {
    simularFetch(respuesta(200, SESION_HABILITADA))
    const router = await routerNuevo()

    await router.push('/bienvenida')

    expect(router.currentRoute.value.name).toBe('inicio')
  })
})
