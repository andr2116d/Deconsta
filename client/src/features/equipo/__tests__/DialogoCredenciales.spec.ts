import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import DialogoCredenciales from '../components/DialogoCredenciales.vue'

describe('DialogoCredenciales', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('copia el usuario y la contraseña al portapapeles', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const dialogo = mount(DialogoCredenciales, {
      props: {
        credenciales: {
          asistente: { nombres: 'Daniela', apellidos: 'Torres' } as never,
          nombre_usuario: 'daniela.torres',
          contrasena_temporal: 'K7mPq2xRt9WbZn',
        },
      },
    })

    const boton = (texto: string) =>
      dialogo.findAll('button').find((b) => b.text().includes(texto))!
    await boton('Copiar usuario y contraseña').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith(
      'Usuario: daniela.torres\nContraseña temporal: K7mPq2xRt9WbZn',
    )
    expect(dialogo.text()).toContain('Copiados')
  })
})
