import { describe, expect, it } from 'vitest'

import { errorArchivo, TAMANO_MAXIMO } from '../composables/useAnalisisDocumento'

const archivo = (nombre: string, tipo: string, bytes = 10) =>
  new File([new Uint8Array(bytes)], nombre, { type: tipo })

describe('errorArchivo', () => {
  it('acepta hasta 10 MB y dice cuánto pesa lo que se pasa', () => {
    expect(errorArchivo(archivo('recibo.jpg', 'image/jpeg', TAMANO_MAXIMO))).toBeNull()
    expect(errorArchivo(archivo('recibo.jpg', 'image/jpeg', TAMANO_MAXIMO + 1))).toContain(
      'el máximo es 10 MB',
    )
  })

  it('sin tipo informado por el sistema, decide por la extensión', () => {
    expect(errorArchivo(archivo('recibo.PDF', ''))).toBeNull()
    expect(errorArchivo(archivo('recibo.zip', ''))).toContain('Sube una imagen JPG')
  })

  it('explica qué hacer con una foto HEIC del iPhone', () => {
    expect(errorArchivo(archivo('IMG_0001.HEIC', ''))).toContain('HEIC')
    expect(errorArchivo(archivo('foto', 'image/heic'))).toContain('HEIC')
  })
})
