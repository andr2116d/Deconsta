import { describe, expect, it } from 'vitest'

import { rutasDelEspacio, SECCIONES, seccionesDe, textoPorRol } from '../secciones'

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

  it('agrupa las pestañas de Mi cuenta bajo una sola ruta', () => {
    const cuenta = rutasDelEspacio().find((r) => r.path === 'cuenta')
    expect(cuenta?.children?.map((r) => [r.path, r.name])).toEqual([
      ['', 'mis-datos'],
      ['acceso', 'acceso-cuenta'],
      ['permisos', 'permisos'],
      ['privacidad', 'privacidad'],
    ])
  })

  it('registrar asistente es una pantalla interna de Mi equipo, sin pestaña propia', () => {
    const pestanas = seccionesDe('gerente', 'pestana').map((s) => s.nombre)
    expect(pestanas).not.toContain('registrar-asistente')
    expect(SECCIONES.find((s) => s.nombre === 'registrar-asistente')?.padre).toBe('equipo')
  })

  it('no repite nombres ni rutas', () => {
    expect(new Set(SECCIONES.map((s) => s.nombre)).size).toBe(SECCIONES.length)
    expect(new Set(SECCIONES.map((s) => s.ruta)).size).toBe(SECCIONES.length)
  })
})
