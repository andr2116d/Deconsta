import { describe, expect, it } from 'vitest'

import { camposCambiados, normalizarNombreUsuario, requiereContrasena } from '../datos'
import type { DatosEditables } from '../types'

const ORIGINAL: DatosEditables = {
  nombres: 'Valentina',
  apellidos: 'Ramos Díaz',
  correo: 'valentina@ejemplo.pe',
  telefono: '987654321',
  tipo_documento: 'dni',
  numero_documento: '45678912',
  nombre_recibos: null,
}

describe('cambios reales de los datos personales', () => {
  it('no cuenta espacios, mayúsculas del correo ni separadores del teléfono', () => {
    const casi = {
      ...ORIGINAL,
      nombres: '  Valentina ',
      apellidos: 'Ramos   Díaz',
      correo: ' VALENTINA@ejemplo.pe',
      telefono: '987 654-321',
      nombre_recibos: '   ',
    }
    expect(camposCambiados(ORIGINAL, casi)).toEqual([])
  })

  it('detecta solo los campos que cambian y cuáles piden contraseña', () => {
    const telefono = camposCambiados(ORIGINAL, { ...ORIGINAL, telefono: '912345678' })
    const correo = camposCambiados(ORIGINAL, { ...ORIGINAL, correo: 'otro@ejemplo.pe' })

    expect(telefono).toEqual(['telefono'])
    expect(requiereContrasena(telefono)).toBe(false)
    expect(requiereContrasena(correo)).toBe(true)
  })

  it('normaliza el usuario como el backend', () => {
    expect(normalizarNombreUsuario('  Valentina.Ramos ')).toBe('valentina.ramos')
  })
})
