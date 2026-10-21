import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useSesionStore } from '../stores/sesion'
import { respuesta, SESION, simularFetch } from './respuestas'

const CREDENCIALES = { nombre_usuario: 'lucia.vega', contrasena: 'Temporal-2026' }
const INGRESO = { ...SESION, pasos_pendientes: [], primer_ingreso: true }

describe('recordatorio de la contraseña temporal', () => {
  beforeEach(() => {
    sessionStorage.clear()
    setActivePinia(createPinia())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('no vuelve al recargar después de posponerlo', async () => {
    simularFetch(respuesta(200, INGRESO))
    const sesion = useSesionStore()
    await sesion.ingresar(CREDENCIALES)
    expect(sesion.recordarContrasena).toBe(true)

    sesion.posponerCambioContrasena()
    expect(sesion.recordarContrasena).toBe(false)

    // Una recarga crea un estado nuevo con la misma sesión del backend.
    setActivePinia(createPinia())
    simularFetch(respuesta(200, SESION))
    const recargada = useSesionStore()
    await recargada.comprobar()
    expect(recargada.recordarContrasena).toBe(false)
  })

  it('vuelve en el siguiente ingreso mientras siga siendo temporal', async () => {
    simularFetch(respuesta(200, INGRESO), respuesta(204), respuesta(200, INGRESO))
    const sesion = useSesionStore()
    await sesion.ingresar(CREDENCIALES)
    sesion.posponerCambioContrasena()

    await sesion.salir()
    await sesion.ingresar(CREDENCIALES)

    expect(sesion.recordarContrasena).toBe(true)
  })
})
