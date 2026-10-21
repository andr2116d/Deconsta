import { describe, expect, it } from 'vitest'

import { avisoNombre, claveNombre, filtrarNombreCategoria } from '../catalogo'
import type { Categoria } from '../types'

const LUZ = { id: 'c1', nombre: 'Luz', archivada: false } as Categoria
const GAS = { id: 'c2', nombre: 'Gas', archivada: true } as Categoria

describe('nombre de una categoría', () => {
  it('compara sin mayúsculas, tildes ni espacios repetidos, como el backend', () => {
    expect(claveNombre('  Teléfono   e INTERNET ')).toBe('telefono e internet')
  })

  it('no deja escribir lo que nunca sería válido', () => {
    expect(filtrarNombreCategoria('  <Luz>  del   local!')).toBe('Luz del local')
    expect(filtrarNombreCategoria('Agua & desagüe (casa)')).toBe('Agua & desagüe (casa)')
    expect(filtrarNombreCategoria('x'.repeat(50))).toHaveLength(40)
  })

  it('avisa mientras se escribe si es muy corto o ya existe', () => {
    expect(avisoNombre('L', [LUZ])).toBe('Usa al menos 2 caracteres.')
    expect(avisoNombre('LUZ', [LUZ])).toBe('Ya tienes una categoría llamada «Luz».')
    expect(avisoNombre('gas', [GAS])).toContain('archivada: puedes reactivarla')
    // Al editarla, su propio nombre no cuenta como repetido.
    expect(avisoNombre('Luz', [LUZ], 'c1')).toBeUndefined()
  })
})
