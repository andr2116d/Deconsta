import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import DialogoCategoria from '../components/DialogoCategoria.vue'
import type { Categoria } from '../types'

const AGUA: Categoria = {
  id: 'c1',
  nombre: 'Agua',
  descripcion: null,
  color: 'azul',
  icono: 'agua',
  archivada: false,
  creado_en: '2026-10-21T10:00:00Z',
  actualizado_en: '2026-10-21T10:00:00Z',
  archivado_en: null,
}

function montar(props: Partial<InstanceType<typeof DialogoCategoria>['$props']> = {}) {
  const dialogo = mount(DialogoCategoria, {
    props: { abierto: true, ...props },
    attachTo: document.body,
  })
  const nombre = () => {
    const label = dialogo.findAll('label').find((l) => l.text() === 'Nombre')
    return dialogo.get(`#${label!.attributes('for')}`)
  }
  const guardar = () => dialogo.get('button[type="submit"]')
  return { dialogo, nombre, guardar }
}

describe('DialogoCategoria', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('pide el nombre y no envía nada si falta', async () => {
    const fetch = simularFetch()
    const { dialogo } = montar()

    await dialogo.get('form').trigger('submit')

    expect(dialogo.text()).toContain('Escribe el nombre de la categoría.')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('crea la categoría con el color y el ícono elegidos', async () => {
    const creada = { ...AGUA, nombre: 'Luz del local', color: 'ambar', icono: 'luz' }
    const fetch = simularFetch(respuesta(201, creada))
    const { dialogo, nombre } = montar()

    await nombre().setValue('Luz del local')
    await dialogo.get('input[type="radio"][value="ambar"]').setValue()
    await dialogo.get('input[type="radio"][value="luz"]').setValue()
    await dialogo.get('form').trigger('submit')
    await flushPromises()

    const [ruta, opciones] = fetch.mock.calls[0]!
    expect(ruta).toBe('/api/v1/categorias')
    expect(JSON.parse(opciones!.body as string)).toEqual({
      nombre: 'Luz del local',
      descripcion: null,
      color: 'ambar',
      icono: 'luz',
    })
    expect(dialogo.emitted('guardada')).toEqual([[creada, true]])
  })

  it('ofrece reactivar la categoría archivada con el mismo nombre', async () => {
    const mensaje =
      'Ya tienes una categoría archivada llamada «Agua». Reactívala para volver a usarla.'
    simularFetch(
      respuesta(409, {
        code: 'CATEGORIA_DUPLICADA',
        detail: mensaje,
        fields: { nombre: mensaje },
        existing_category: { id: 'c1', archivada: true },
      }),
    )
    const { dialogo, nombre } = montar()

    await nombre().setValue('agua')
    await dialogo.get('form').trigger('submit')
    await flushPromises()

    expect(dialogo.text()).toContain(mensaje)
    await dialogo
      .findAll('button')
      .find((b) => b.text() === 'Reactivar la categoría archivada')!
      .trigger('click')
    expect(dialogo.emitted('reactivar')).toEqual([['c1']])
  })

  it('al editar, solo permite guardar con un cambio real', async () => {
    const { nombre, guardar } = montar({ categoria: AGUA })

    expect(guardar().attributes('disabled')).toBeDefined()
    await nombre().setValue('Agua ')
    expect(guardar().attributes('disabled')).toBeDefined()
    await nombre().setValue('Agua y desagüe')
    expect(guardar().attributes('disabled')).toBeUndefined()
  })
})
