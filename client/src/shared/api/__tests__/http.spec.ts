import { afterEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import { ErrorApi, solicitar } from '../http'

describe('solicitar', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('convierte la estructura de error del backend en un ErrorApi', async () => {
    simularFetch(
      respuesta(429, { code: 'DEMASIADAS_SOLICITUDES', detail: 'Espera.', retry_after: 12 }),
    )

    const error = await solicitar('/auth/me').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ErrorApi)
    expect(error).toMatchObject({ estado: 429, codigo: 'DEMASIADAS_SOLICITUDES', reintentarEn: 12 })
  })

  it('no expone respuestas de error sin la estructura esperada', async () => {
    simularFetch(new Response('<html>502 Bad Gateway</html>', { status: 502 }))

    const error = await solicitar('/auth/me').catch((e: unknown) => e)

    expect(error).toMatchObject({ estado: 502, codigo: 'ERROR_INTERNO' })
    expect((error as Error).message).not.toContain('Bad Gateway')
  })

  it('envía la cookie solo al mismo origen', async () => {
    const fetch = simularFetch(respuesta(204))
    await solicitar('/auth/logout', { method: 'POST' })
    expect(fetch.mock.calls[0]?.[1]).toMatchObject({ credentials: 'same-origin' })
  })
})
