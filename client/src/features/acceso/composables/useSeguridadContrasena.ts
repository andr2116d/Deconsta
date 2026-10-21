import { computed, toValue, type MaybeRefOrGetter } from 'vue'

/**
 * Indicador visual de seguridad. Solo orienta mientras se escribe: la política la aplica el
 * backend y sus mensajes se muestran al guardar.
 */
export const LONGITUD_MINIMA = 10

export interface Requisito {
  clave: string
  texto: string
  cumplido: boolean
}

const NIVELES = ['Muy débil', 'Débil', 'Aceptable', 'Segura', 'Muy segura'] as const

export function useSeguridadContrasena(
  contrasena: MaybeRefOrGetter<string>,
  nombreUsuario: MaybeRefOrGetter<string>,
) {
  const requisitos = computed<Requisito[]>(() => {
    const valor = toValue(contrasena)
    const usuario = toValue(nombreUsuario).trim().toLowerCase()
    return [
      {
        clave: 'longitud',
        texto: `Al menos ${LONGITUD_MINIMA} caracteres`,
        cumplido: valor.length >= LONGITUD_MINIMA,
      },
      { clave: 'letra', texto: 'Una letra', cumplido: /\p{L}/u.test(valor) },
      { clave: 'numero', texto: 'Un número', cumplido: /\d/.test(valor) },
      {
        clave: 'usuario',
        texto: 'Sin tu nombre de usuario',
        cumplido: valor.length > 0 && (!usuario || !valor.toLowerCase().includes(usuario)),
      },
    ]
  })

  const cumpleRequisitos = computed(() => requisitos.value.every((r) => r.cumplido))

  // 0 a 4. Sin los requisitos mínimos nunca pasa de «Débil».
  const puntaje = computed(() => {
    const valor = toValue(contrasena)
    if (!valor || new Set(valor).size <= 3) return 0
    if (!cumpleRequisitos.value) return valor.length >= 6 ? 1 : 0
    let puntos = 2
    if (/[a-z]/.test(valor) && /[A-Z]/.test(valor)) puntos += 1
    if (/[^\p{L}\d]/u.test(valor)) puntos += 1
    if (valor.length >= 14) puntos += 1
    return Math.min(4, puntos)
  })

  const nivel = computed<string>(() => NIVELES[puntaje.value] ?? NIVELES[0])

  return { requisitos, puntaje, nivel, cumpleRequisitos }
}
