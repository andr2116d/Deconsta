import { describe, expect, it } from 'vitest'
import { ref } from 'vue'

import { useSeguridadContrasena } from '../composables/useSeguridadContrasena'

function evaluar(contrasena: string) {
  return useSeguridadContrasena(ref(contrasena), ref('lucia.vega'))
}

describe('useSeguridadContrasena', () => {
  it.each([
    ['', 0],
    ['abc', 0],
    ['aaaaaaaaaaaa1', 0],
    ['letrasSolamente', 1],
    ['ciruela2026', 2],
    ['Ciruela2026', 3],
    ['Ciruela-Rosa-2026', 4],
  ])('puntúa %j con %i', (contrasena, puntaje) => {
    expect(evaluar(contrasena).puntaje.value).toBe(puntaje)
  })

  it('no considera aceptable una contraseña que incluye el usuario', () => {
    const resultado = evaluar('Lucia.Vega-2026')
    expect(resultado.cumpleRequisitos.value).toBe(false)
    expect(resultado.puntaje.value).toBeLessThan(2)
  })
})
