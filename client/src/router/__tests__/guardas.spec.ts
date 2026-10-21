import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, SESION, simularFetch } from '@/features/acceso/__tests__/respuestas'

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
    simularFetch(respuesta(200, SESION))
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
})
