import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DialogoAccionAsistente from '../components/DialogoAccionAsistente.vue'
import type { Asistente } from '../types'

const DANIELA = { id: 'a1', nombres: 'Daniela', apellidos: 'Torres' } as Asistente

describe('DialogoAccionAsistente', () => {
  it('explica el restablecimiento y envía el motivo escrito', async () => {
    const dialogo = mount(DialogoAccionAsistente, {
      props: { accion: { tipo: 'restablecer', asistente: DANIELA }, enviando: false },
    })

    expect(dialogo.text()).toContain('¿Restablecer la contraseña de Daniela Torres?')
    expect(dialogo.text()).toContain('Su contraseña actual dejará de servir')
    await dialogo.get('textarea').setValue('  Olvidó su contraseña ')
    await dialogo
      .findAll('button')
      .find((b) => b.text() === 'Restablecer contraseña')!
      .trigger('click')

    expect(dialogo.emitted('confirmar')).toEqual([['Olvidó su contraseña']])
  })
})
