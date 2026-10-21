import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import FormularioNombreUsuario from '../components/FormularioNombreUsuario.vue'
import { CUENTA } from './respuestas'

function montar(cuenta = CUENTA) {
  const formulario = mount(FormularioNombreUsuario, { props: { cuenta }, attachTo: document.body })
  const boton = () => formulario.findAll('button').find((b) => b.text() === 'Cambiar usuario')!
  return { formulario, usuario: formulario.get('input'), boton }
}

describe('FormularioNombreUsuario', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('muestra los cambios que quedan y no se activa sin un cambio válido', async () => {
    const { formulario, usuario, boton } = montar()
    expect(formulario.text()).toContain('Te quedan 3 cambios de usuario este mes.')
    expect(boton().attributes('disabled')).toBeDefined()

    await usuario.setValue(' VALENTINA.RAMOS ')
    expect(boton().attributes('disabled')).toBeDefined()

    await usuario.setValue('v!')
    expect(formulario.text()).toContain('Usa de 3 a 40 letras minúsculas')
  })

  it('sin cupo, el campo queda bloqueado hasta el mes siguiente', () => {
    const { formulario, usuario } = montar({
      ...CUENTA,
      cambios_nombre_usuario: { ...CUENTA.cambios_nombre_usuario, usados: 3, restantes: 0 },
    })
    expect(usuario.attributes('disabled')).toBeDefined()
    expect(formulario.text()).toContain('Ya usaste tus cambios de este mes.')
  })

  it('envía el usuario normalizado con la contraseña', async () => {
    const fetch = simularFetch(
      respuesta(200, {
        ...CUENTA,
        nombre_usuario: 'vale.ramos',
        cambios_nombre_usuario: { ...CUENTA.cambios_nombre_usuario, usados: 1, restantes: 2 },
      }),
    )
    const { formulario, usuario } = montar()
    await usuario.setValue('Vale.Ramos')
    await formulario.findAll('input')[1]!.setValue('Secreta-2026')

    await formulario.get('form').trigger('submit')
    await flushPromises()

    expect(JSON.parse(fetch.mock.calls[0]![1]!.body as string)).toEqual({
      nombre_usuario: 'vale.ramos',
      contrasena_actual: 'Secreta-2026',
    })
    expect(formulario.text()).toContain('Tu usuario ahora es @vale.ramos.')
  })
})
