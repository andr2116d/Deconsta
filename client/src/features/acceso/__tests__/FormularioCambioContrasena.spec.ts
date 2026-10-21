import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import FormularioCambioContrasena from '../components/FormularioCambioContrasena.vue'
import { useSesionStore } from '../stores/sesion'
import { respuesta, SESION, simularFetch } from './respuestas'

async function montar() {
  const sesion = useSesionStore()
  sesion.sesion = structuredClone(SESION) as typeof sesion.sesion
  const formulario = mount(FormularioCambioContrasena, { props: { inicial: true } })
  const campos = formulario.findAll('input')
  return { formulario, sesion, actual: campos[0]!, nueva: campos[1]!, confirmacion: campos[2]! }
}

describe('FormularioCambioContrasena', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('pide repetir la misma contraseña antes de enviarla', async () => {
    const fetch = simularFetch()
    const { formulario, actual, nueva, confirmacion } = await montar()
    await actual.setValue('Temporal-1')
    await nueva.setValue('Ciruela-2026')
    await confirmacion.setValue('Ciruela-2025')

    await formulario.find('form').trigger('submit')

    expect(formulario.text()).toContain('Las contraseñas no coinciden.')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('advierte antes de enviar si la nueva contraseña es igual a la actual', async () => {
    const fetch = simularFetch()
    const { formulario, actual, nueva, confirmacion } = await montar()
    await actual.setValue('Ciruela-2026')
    await nueva.setValue('Ciruela-2026')
    await confirmacion.setValue('Ciruela-2026')

    expect(formulario.text()).toContain('La nueva contraseña debe ser distinta de la actual.')
    expect(formulario.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    await formulario.find('form').trigger('submit')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('muestra junto al campo lo que la política del backend rechaza', async () => {
    simularFetch(
      respuesta(422, {
        code: 'CONTRASENA_INSEGURA',
        detail: 'La nueva contraseña no cumple la política de seguridad.',
        fields: { contrasena_nueva: 'Incluye al menos un número.' },
      }),
    )
    const { formulario, actual, nueva, confirmacion } = await montar()
    await actual.setValue('Temporal-1')
    await nueva.setValue('SoloLetrasLargas')
    await confirmacion.setValue('SoloLetrasLargas')

    await formulario.find('form').trigger('submit')
    await flushPromises()

    expect(nueva.attributes('aria-invalid')).toBe('true')
    expect(formulario.text()).toContain('Incluye al menos un número.')
  })

  it('actualiza el indicador de la sesión al guardar', async () => {
    simularFetch(
      respuesta(200, {
        ...SESION,
        debe_cambiar_contrasena: false,
        pasos_pendientes: ['aceptar_documentos'],
      }),
    )
    const { formulario, sesion, actual, nueva, confirmacion } = await montar()
    await actual.setValue('Temporal-1')
    await nueva.setValue('Ciruela-2026')
    await confirmacion.setValue('Ciruela-2026')

    await formulario.find('form').trigger('submit')
    await flushPromises()

    expect(formulario.emitted('cambiada')).toHaveLength(1)
    expect(sesion.debeCambiarContrasena).toBe(false)
    expect(sesion.pasoActual).toBe('aceptar_documentos')
  })

  it('no ofrece omitir el cambio de la contraseña temporal', async () => {
    const { formulario } = await montar()
    const textos = formulario.findAll('button').map((b) => b.text())
    expect(textos).not.toContain('Omitir por ahora')
    expect(textos).not.toContain('Volver')
  })
})
