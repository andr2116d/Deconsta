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
      'Por pagar',
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

  it('agrupa las reglas y las categorías en las pestañas de Límites y categorías', () => {
    const configuracion = rutasDelEspacio().find((r) => r.path === 'configuracion')
    expect(configuracion?.children?.map((r) => [r.path, r.name])).toEqual([
      ['', 'configuracion'],
      ['categorias', 'categorias'],
    ])
    expect(etiquetas('gerente', 'cuenta').filter((e) => e === 'Categorías')).toEqual([])
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
