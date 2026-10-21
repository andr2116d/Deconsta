import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import DialogoTitular from '../components/DialogoTitular.vue'

function montar() {
  const dialogo = mount(DialogoTitular, { props: { abierto: true }, attachTo: document.body })
  const campo = (etiqueta: string) => {
    const label = dialogo.findAll('label').find((l) => l.text().startsWith(etiqueta))
    return dialogo.get(`#${label!.attributes('for')}`)
  }
  return { dialogo, campo }
}

describe('DialogoTitular', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('pide el nombre y la autorización del titular y no envía nada si faltan', async () => {
    const fetch = simularFetch()
    const { dialogo } = montar()

    await dialogo.get('form').trigger('submit')

    expect(dialogo.text()).toContain('Escribe el nombre como aparece en sus recibos.')
    expect(dialogo.text()).toContain('Confirma que esta persona te autorizó')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('agrega el titular con su documento y su autorización', async () => {
    const titular = { id: 't1', nombre: 'María Ruiz Soto', relacion: 'Esposa' }
    const fetch = simularFetch(respuesta(201, titular))
    const { dialogo, campo } = montar()

    await campo('Nombre completo').setValue('María Ruiz Soto')
    await campo('Relación').setValue('Esposa')
    await campo('Documento').setValue('dni')
    await campo('Número de DNI').setValue('41a234568')
    await campo('Esta persona me autorizó').setValue(true)
    await dialogo.get('form').trigger('submit')
    await flushPromises()

    const [ruta, opciones] = fetch.mock.calls[0]!
    expect(ruta).toBe('/api/v1/reglas/titulares')
    expect(JSON.parse(opciones!.body as string)).toEqual({
      nombre: 'María Ruiz Soto',
      relacion: 'Esposa',
      tipo_documento: 'dni',
      numero_documento: '41234568',
      autorizacion_declarada: true,
    })
    expect(dialogo.emitted('guardado')).toEqual([[titular, true]])
  })

  it('muestra junto al campo por qué el backend lo rechazó', async () => {
    const mensaje =
      'Ese documento es el tuyo: tus recibos ya se reconocen con tus datos de Mi cuenta.'
    simularFetch(
      respuesta(422, {
        code: 'TITULAR_ES_GERENTE',
        detail: mensaje,
        fields: { numero_documento: mensaje },
      }),
    )
    const { dialogo, campo } = montar()

    await campo('Nombre completo').setValue('Valentina Ramos')
    await campo('Documento').setValue('dni')
    await campo('Número de DNI').setValue('45678912')
    await campo('Esta persona me autorizó').setValue(true)
    await dialogo.get('form').trigger('submit')
    await flushPromises()

    expect(dialogo.text()).toContain(mensaje)
    expect(dialogo.emitted('guardado')).toBeUndefined()
  })
})
