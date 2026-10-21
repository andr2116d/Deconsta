import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { respuesta, SESION_HABILITADA, simularFetch } from '@/features/acceso/__tests__/respuestas'

import PasoDatos from '../components/PasoDatos.vue'

const CUENTA = {
  id: '1',
  rol: 'asistente',
  nombre_usuario: 'daniela.torres',
  nombres: 'Daniela',
  apellidos: 'Torres',
  correo: null,
  telefono: '987654321',
  tipo_documento: 'dni',
  numero_documento: '44556677',
  nombre_recibos: null,
  cargo: null,
  debe_cambiar_contrasena: true,
  contrasena_actualizada_en: '2026-10-21T10:00:00Z',
  cambios_nombre_usuario: {
    maximo: 3,
    usados: 0,
    restantes: 3,
    renueva_en: '2026-11-01T00:00:00-05:00',
  },
}

describe('PasoDatos', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('exige el correo y la confirmación antes de enviar, y luego entrega la sesión', async () => {
    const fetch = simularFetch(respuesta(200, CUENTA), respuesta(200, SESION_HABILITADA))
    const paso = mount(PasoDatos, { attachTo: document.body })
    await flushPromises()

    await paso.get('form').trigger('submit')
    expect(paso.text()).toContain('Escribe tu correo.')
    expect(paso.text()).toContain('Marca la casilla para confirmar tus datos.')
    expect(fetch).toHaveBeenCalledTimes(1)

    await paso.get('input[type="email"]').setValue('dani@ejemplo.pe')
    await paso.get('input[type="checkbox"]').setValue(true)
    await paso.get('form').trigger('submit')
    await flushPromises()

    const enviado = JSON.parse(fetch.mock.calls[1]![1]!.body as string)
    expect(enviado).toMatchObject({ correo: 'dani@ejemplo.pe', numero_documento: '44556677' })
    expect(paso.emitted('confirmada')).toHaveLength(1)
  })
})
