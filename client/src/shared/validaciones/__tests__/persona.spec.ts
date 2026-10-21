import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ref } from 'vue'

import CampoDocumento from '@/shared/components/CampoDocumento.vue'

import {
  avisoCelular,
  avisoCorreo,
  avisoDocumento,
  filtrarCarne,
  filtrarCelular,
  filtrarDni,
  filtrarNombre,
} from '../persona'

describe('filtros de datos personales', () => {
  it('no deja escribir lo que el dato nunca admite', () => {
    expect(filtrarDni('12ab345678901')).toBe('12345678')
    expect(filtrarCarne('ab-12 3456789xyz')).toBe('AB123456789X')
    expect(filtrarCelular('+51 987 654 321')).toBe('987654321')
    expect(filtrarCelular('98a7')).toBe('987')
    expect(filtrarNombre('María José 2#')).toBe('María José ')
  })

  it('avisa lo que falta mientras se escribe', () => {
    expect(avisoDocumento('dni', '1234')).toBe('El DNI tiene 8 dígitos. Faltan 4 dígitos.')
    expect(avisoDocumento('dni', '1234567')).toContain('Falta 1 dígito.')
    expect(avisoDocumento('ce', '12345678')).toContain('Falta 1 carácter.')
    expect(avisoCelular('812')).toBe('Un celular peruano empieza con 9.')
    expect(avisoCelular('98765432')).toBe('Falta 1 dígito.')
    expect(avisoCelular('987654321')).toBeUndefined()
    expect(avisoCorreo('lucia')).toContain('Incluye la @')
    expect(avisoCorreo('lucia@empresa')).toContain('extensión')
    expect(avisoCorreo('lucia@empresa.pe')).toBeUndefined()
  })
})

describe('CampoDocumento', () => {
  it('filtra lo escrito según el tipo y lo vuelve a filtrar al cambiarlo', async () => {
    const tipo = ref<'dni' | 'ce'>('ce')
    const numero = ref('')
    const campo = mount(CampoDocumento, {
      props: {
        tipo: tipo.value,
        numero: numero.value,
        'onUpdate:tipo': (v: 'dni' | 'ce') => campo.setProps({ tipo: v }),
        'onUpdate:numero': (v: string) => campo.setProps({ numero: v }),
      },
    })
    const entrada = campo.get('input')

    await entrada.setValue('ab12345cd')
    expect(campo.props('numero')).toBe('AB12345CD')

    await campo.get('select').setValue('dni')
    expect(campo.props('numero')).toBe('12345')
    expect(campo.text()).toContain('Faltan 3 dígitos.')
  })
})
