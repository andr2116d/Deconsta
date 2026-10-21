import { vi } from 'vitest'

export function respuesta(estado: number, cuerpo?: unknown): Response {
  return new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), {
    status: estado,
    headers: { 'Content-Type': 'application/json' },
  })
}

export const SESION = {
  usuario: { id: '1', nombre_usuario: 'lucia.vega', nombres: 'Lucía', rol: 'asistente' },
  debe_cambiar_contrasena: true,
  pasos_pendientes: ['cambiar_contrasena'],
}

/** Cuenta que ya completó el primer ingreso. */
export const SESION_HABILITADA = {
  ...SESION,
  debe_cambiar_contrasena: false,
  pasos_pendientes: [],
}

/** Simula fetch con respuestas en orden y devuelve el mock para revisar las llamadas. */
export function simularFetch(...respuestas: Array<Response | Promise<Response>>) {
  const mock = vi.fn<typeof fetch>()
  for (const r of respuestas) mock.mockImplementationOnce(() => Promise.resolve(r))
  vi.stubGlobal('fetch', mock)
  return mock
}
