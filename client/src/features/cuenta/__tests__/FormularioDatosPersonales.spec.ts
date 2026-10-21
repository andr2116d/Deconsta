import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, SESION_HABILITADA, simularFetch } from '@/features/acceso/__tests__/respuestas'
import { useSesionStore } from '@/features/acceso/stores/sesion'

import FormularioDatosPersonales from '../components/FormularioDatosPersonales.vue'
import { CUENTA } from './respuestas'

function montar(cuenta = CUENTA) {
  useSesionStore().actualizar(structuredClone(SESION_HABILITADA) as never)
  const formulario = mount(FormularioDatosPersonales, {
    props: { cuenta },
    attachTo: document.body,
  })
  const campo = (etiqueta: string) => {
    const label = formulario.findAll('label').find((l) => l.text() === etiqueta)
    return formulario.get(`#${label!.attributes('for')}`)
  }
  const guardar = () => formulario.findAll('button').find((b) => b.text() === 'Guardar mis datos')!
  return { formulario, campo, guardar }
}

describe('FormularioDatosPersonales', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('solo activa «Guardar» con un cambio real', async () => {
    const { campo, guardar } = montar()
    expect(guardar().attributes('disabled')).toBeDefined()

    await campo('Nombres').setValue('Valentina  ')
    expect(guardar().attributes('disabled')).toBeDefined()

    await campo('Teléfono').setValue('912345678')
    expect(guardar().attributes('disabled')).toBeUndefined()
  })

  it('advierte al instante que el número de DNI no se cambia', async () => {
    const { formulario, campo, guardar } = montar()

    await campo('Número de DNI').setValue('45678913')

    expect(formulario.text()).toContain('no se puede cambiar')
    expect(guardar().attributes('disabled')).toBeDefined()
  })

  it('pide la contraseña al cambiar el correo', async () => {
    const fetch = simularFetch()
    const { formulario, campo } = montar()
    await campo('Correo').setValue('nuevo@ejemplo.pe')

    await formulario.get('form').trigger('submit')

    expect(campo('Contraseña actual').attributes('aria-invalid')).toBe('true')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('abre una ventana ordenada si la actualización falla', async () => {
    simularFetch(
      respuesta(409, {
        code: 'DATOS_DUPLICADOS',
        detail: 'Ya existe una cuenta con alguno de estos datos.',
        fields: { correo: 'Ese correo ya pertenece a otra cuenta.' },
      }),
    )
    const { formulario, campo } = montar()
    await campo('Correo').setValue('ajeno@ejemplo.pe')
    await campo('Contraseña actual').setValue('Secreta-2026')

    await formulario.get('form').trigger('submit')
    await flushPromises()

    const ventana = formulario.get('dialog[open]')
    expect(ventana.text()).toContain('No pudimos guardar tus datos')
    expect(ventana.text()).toContain('Ese correo ya pertenece a otra cuenta.')
    expect(campo('Correo').attributes('aria-invalid')).toBe('true')
  })

  it('al guardar actualiza el nombre de la sesión sin recargar', async () => {
    const fetch = simularFetch(respuesta(200, { ...CUENTA, nombres: 'Valentina Sofía' }))
    const { formulario, campo } = montar()
    await campo('Nombres').setValue('Valentina Sofía')

    await formulario.get('form').trigger('submit')
    await flushPromises()

    const enviado = JSON.parse(fetch.mock.calls[0]![1]!.body as string)
    expect(enviado).toMatchObject({ nombres: 'Valentina Sofía', confirmar_cambio_documento: false })
    expect(enviado.contrasena_actual).toBeUndefined()
    expect(useSesionStore().usuario?.nombres).toBe('Valentina Sofía')
  })

  it('la asistente no ve el nombre en recibos', () => {
    const { formulario } = montar({ ...CUENTA, rol: 'asistente' })
    expect(formulario.text()).not.toContain('Nombre como figura en tus recibos')
  })
})
