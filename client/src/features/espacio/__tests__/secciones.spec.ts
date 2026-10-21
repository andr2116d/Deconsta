import { describe, expect, it } from 'vitest'

import { SECCIONES, seccionesDe, textoPorRol } from '../secciones'

const etiquetas = (rol: 'gerente' | 'asistente', ubicacion: Parameters<typeof seccionesDe>[1]) =>
  seccionesDe(rol, ubicacion).map((s) => textoPorRol(s.etiqueta, rol))

describe('secciones del espacio', () => {
  it('muestra a gerencia sus pestañas de decisión', () => {
    expect(etiquetas('gerente', 'pestana')).toEqual([
      'Resumen',
      'Por autorizar',
      'Por verificar',
      'Calendario',
      'Historial',
      'Mi equipo',
    ])
    expect(etiquetas('gerente', 'cuenta')).toContain('Límites y categorías')
  })

  it('muestra a asistencia sus pestañas de ejecución, sin las de gerencia', () => {
    expect(etiquetas('asistente', 'pestana')).toEqual([
      'Mi jornada',
      'Pagos por completar',
      'Mis registros',
      'Calendario',
    ])
    expect(etiquetas('asistente', 'cuenta')).not.toContain('Límites y categorías')
  })

  it('no repite nombres ni rutas', () => {
    expect(new Set(SECCIONES.map((s) => s.nombre)).size).toBe(SECCIONES.length)
    expect(new Set(SECCIONES.map((s) => s.ruta)).size).toBe(SECCIONES.length)
  })
})
