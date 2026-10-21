import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { respuesta, simularFetch } from '@/features/acceso/__tests__/respuestas'

import FormularioAsistente from '../components/FormularioAsistente.vue'
import { sugerirUsuario } from '../credenciales'

const ASISTENTE = {
  id: 'a1',
  nombre_usuario: 'daniela.torres',
  nombres: 'Daniela',
  apellidos: 'Torres',
  cargo: null,
  telefono: '987654321',
  correo: null,
  tipo_documento: 'dni',
  documento: '•••• 6677',
  estado: 'pendiente',
  causa_bloqueo: null,
  bloqueada: false,
  debe_cambiar_contrasena: true,
  ultimo_ingreso_en: null,
}

function montar() {
  const formulario = mount(FormularioAsistente, { attachTo: document.body })
  const campo = (etiqueta: string) => {
    const label = formulario.findAll('label').find((l) => l.text() === etiqueta)
    return formulario.get(`#${label!.attributes('for')}`)
  }
  const crear = () => formulario.get('button[type="submit"]')
  return { formulario, campo, crear }
}

async function completar(campo: ReturnType<typeof montar>['campo']) {
  await campo('Nombres').setValue('Daniela')
  await campo('Apellidos').setValue('Torres Ríos')
  await campo('Celular').setValue('987654321')
  await campo('Número de DNI').setValue('44556677')
}

describe('FormularioAsistente', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('dice qué falta en cada campo obligatorio y no envía nada', async () => {
    const fetch = simularFetch()
    const { formulario } = montar()

    await formulario.get('form').trigger('submit')

    expect(formulario.text()).toContain('Escribe sus nombres.')
    expect(formulario.text()).toContain('Escribe sus apellidos.')
    expect(formulario.text()).toContain('Escribe su número de celular.')
    expect(formulario.text()).toContain('Escribe su número de documento.')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('bloquea el botón mientras se crea la cuenta y entrega las credenciales', async () => {
    let responder!: (r: Response) => void
    const fetch = vi.fn<typeof globalThis.fetch>(
      () => new Promise<Response>((r) => (responder = r)),
    )
    vi.stubGlobal('fetch', fetch)
    const { formulario, campo, crear } = montar()
    await completar(campo)

    await formulario.get('form').trigger('submit')
    await formulario.get('form').trigger('submit')

    expect(crear().attributes('disabled')).toBeDefined()
    expect(crear().attributes('aria-busy')).toBe('true')
    expect(fetch).toHaveBeenCalledTimes(1)
    const enviado = JSON.parse(fetch.mock.calls[0]![1]!.body as string)
    expect(enviado).toMatchObject({ nombre_usuario: null, contrasena: null, cargo: null })

    responder(
      respuesta(201, {
        asistente: ASISTENTE,
        nombre_usuario: 'daniela.torres',
        contrasena_temporal: 'K7mPq2xRt9WbZn',
      }),
    )
    await flushPromises()

    expect(crear().attributes('disabled')).toBeUndefined()
    expect(formulario.emitted('creada')?.[0]?.[0]).toMatchObject({
      nombre_usuario: 'daniela.torres',
    })
  })

  it('si la persona fue eliminada antes, ofrece recuperarla o crear otra', async () => {
    simularFetch(
      respuesta(409, {
        code: 'ASISTENTE_ELIMINADA',
        detail: 'Ya habías registrado a esta persona.',
        deleted_account: { id: 'a1', nombre_usuario: 'daniela.torres' },
      }),
    )
    const { formulario, campo } = montar()
    await completar(campo)

    await formulario.get('form').trigger('submit')
    await flushPromises()

    const ventana = formulario.get('dialog[open]')
    expect(ventana.text()).toContain('Ya registraste a esta persona antes.')
    expect(ventana.text()).toContain('@daniela.torres')
    expect(ventana.text()).toContain('Recuperar su cuenta')
    expect(ventana.text()).toContain('Crear una cuenta nueva desde cero')
  })

  it('sugiere el usuario como lo genera el backend', () => {
    expect(sugerirUsuario('Daniela Sofía', 'Torres Ríos')).toBe('daniela.torres')
    expect(sugerirUsuario('Ñuflo', 'Muñoz')).toBe('nuflo.munoz')
  })
})
