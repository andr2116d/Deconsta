import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { respuesta, SESION_HABILITADA, simularFetch } from '@/features/acceso/__tests__/respuestas'
import type { Usuario } from '@/features/acceso/types'

import PasoPrivacidad from '../components/PasoPrivacidad.vue'
import type { DocumentoLegal } from '../types'

function documento(tipo: DocumentoLegal['tipo'], version: number): DocumentoLegal {
  return {
    tipo,
    version,
    titulo: tipo === 'terminos' ? 'Términos de uso' : 'Política de privacidad',
    resumen: 'Resumen',
    secciones: [{ titulo: 'Qué es Deconsta', parrafos: ['Un espacio de trabajo.'] }],
    vigente_desde: '2026-10-21T07:00:00Z',
    aceptado_en: null,
  }
}

const DOCUMENTOS = [documento('privacidad', 1), documento('terminos', 2)]

async function montar() {
  const paso = mount(PasoPrivacidad, {
    props: {
      usuario: SESION_HABILITADA.usuario as Usuario,
      saliendo: false,
    },
  })
  await flushPromises()
  return paso
}

describe('PasoPrivacidad', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('no envía nada hasta marcar las dos casillas', async () => {
    const fetch = simularFetch(respuesta(200, DOCUMENTOS))
    const paso = await montar()
    await paso.find('input[name="terminos"]').setValue(true)

    await paso.find('form').trigger('submit')

    expect(paso.text()).toContain('Marca las dos casillas para continuar.')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('leer un documento no lo marca como aceptado', async () => {
    simularFetch(respuesta(200, DOCUMENTOS))
    const paso = await montar()

    const leer = paso.findAll('button').find((b) => b.text() === 'Leer los términos de uso')!
    await leer.trigger('click')

    expect(paso.text()).toContain('Versión 2 · vigente desde el')
    expect(paso.text()).toContain('Un espacio de trabajo.')
    expect((paso.find('input[name="terminos"]').element as HTMLInputElement).checked).toBe(false)
  })

  it('acepta exactamente las versiones que se leyeron', async () => {
    const fetch = simularFetch(respuesta(200, DOCUMENTOS), respuesta(200, SESION_HABILITADA))
    const paso = await montar()
    await paso.find('input[name="terminos"]').setValue(true)
    await paso.find('input[name="privacidad"]').setValue(true)

    await paso.find('form').trigger('submit')
    await flushPromises()

    const [ruta, opciones] = fetch.mock.calls[1]!
    expect(ruta).toBe('/api/v1/documentos-legales/aceptacion')
    expect(JSON.parse(String(opciones?.body))).toEqual({
      documentos: [
        { tipo: 'terminos', version: 2 },
        { tipo: 'privacidad', version: 1 },
      ],
    })
    expect(paso.emitted('aceptada')).toEqual([[SESION_HABILITADA]])
  })

  it('si cambió una versión, recarga los documentos y pide marcar de nuevo', async () => {
    simularFetch(
      respuesta(200, DOCUMENTOS),
      respuesta(409, {
        code: 'DOCUMENTOS_DESACTUALIZADOS',
        detail: 'Los términos o la política de privacidad cambiaron mientras los leías.',
      }),
      respuesta(200, [documento('privacidad', 1), documento('terminos', 3)]),
    )
    const paso = await montar()
    await paso.find('input[name="terminos"]').setValue(true)
    await paso.find('input[name="privacidad"]').setValue(true)

    await paso.find('form').trigger('submit')
    await flushPromises()

    expect(paso.text()).toContain('Hay una versión nueva')
    expect(paso.text()).toContain('Versión 3.')
    expect((paso.find('input[name="terminos"]').element as HTMLInputElement).checked).toBe(false)
    expect(paso.emitted('aceptada')).toBeUndefined()
  })
})
