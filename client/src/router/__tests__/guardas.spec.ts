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

  it('deja entrar al espacio con la contraseña temporal si no queda ningún paso', async () => {
    simularFetch(respuesta(200, { ...SESION, pasos_pendientes: [] }))
    const router = await routerNuevo()

    await router.push('/calendario')

    expect(router.currentRoute.value.name).toBe('calendario')
  })

  it('lleva al inicio propio a quien abre una sección de otro rol', async () => {
    simularFetch(respuesta(200, SESION_HABILITADA))
    const router = await routerNuevo()

    await router.push('/por-autorizar')

    expect(router.currentRoute.value.name).toBe('inicio')
  })

  it('pone en el título de la pestaña el nombre de la sección según el rol', async () => {
    simularFetch(respuesta(200, SESION_HABILITADA))
    const router = await routerNuevo()

    await router.push('/')

    expect(router.currentRoute.value.name).toBe('inicio')
    expect(document.title).toBe('Mi jornada · Deconsta')
  })

  it('saca de la bienvenida a quien ya completó los pasos', async () => {
    simularFetch(respuesta(200, SESION_HABILITADA))
    const router = await routerNuevo()

    await router.push('/bienvenida')

    expect(router.currentRoute.value.name).toBe('inicio')
  })
})
