import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import type { Usuario } from '@/features/acceso/types'

import MenuCuenta from '../components/MenuCuenta.vue'
import { rutasDelEspacio } from '../secciones'

const GERENTE: Usuario = {
  id: '1',
  nombre_usuario: 'valentina.ramos',
  nombres: 'Valentina',
  rol: 'gerente',
}

async function montar(contrasenaTemporal = false) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<RouterView/>' }, children: rutasDelEspacio() }],
  })
  await router.push('/inicio')
  return mount(MenuCuenta, {
    props: { usuario: GERENTE, contrasenaTemporal, saliendo: false },
    global: { plugins: [router] },
    attachTo: document.body,
  })
}

describe('MenuCuenta', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('despliega la tarjeta de la cuenta y la cierra con Escape devolviendo el foco', async () => {
    const menu = await montar()
    const boton = menu.get('button[aria-expanded]')

    await boton.trigger('click')
    expect(boton.attributes('aria-expanded')).toBe('true')
    expect(menu.text()).toContain('@valentina.ramos')
    expect(menu.text()).toContain('Límites y categorías')
    expect(menu.text()).not.toContain('Tu contraseña sigue siendo temporal')

    await menu.get(`#${boton.attributes('aria-controls')}`).trigger('keydown', { key: 'Escape' })
    expect(boton.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(boton.element)
  })

  it('se cierra al presionar fuera de la tarjeta', async () => {
    const menu = await montar()
    await menu.get('button[aria-expanded]').trigger('click')

    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await menu.vm.$nextTick()

    expect(menu.get('button[aria-expanded]').attributes('aria-expanded')).toBe('false')
  })

  it('recuerda la contraseña temporal y pide abrir su ventana', async () => {
    const menu = await montar(true)
    await menu.get('button[aria-expanded]').trigger('click')

    const recordatorio = menu
      .findAll('button')
      .find((b) => b.text().includes('Tu contraseña sigue siendo temporal'))
    expect(recordatorio).toBeDefined()
    await recordatorio!.trigger('click')

    expect(menu.emitted('cambiar-contrasena')).toHaveLength(1)
    expect(menu.get('button[aria-expanded]').attributes('aria-expanded')).toBe('false')
  })

  it('lleva a las pestañas de Mi cuenta y señala la contraseña temporal', async () => {
    const menu = await montar(true)
    await menu.get('button[aria-expanded]').trigger('click')

    const enlaces = menu.findAll('a')
    expect(enlaces.map((a) => a.get('.flex-1').text())).toEqual([
      'Mis datos personales',
      'Usuario y contraseña',
      'Mi rol y permisos',
      'Privacidad y autorizaciones',
      'Límites y categorías',
    ])
    expect(enlaces[1]!.attributes('href')).toBe('/cuenta/acceso')
    expect(enlaces[1]!.text()).toContain('Temporal')
  })
})
