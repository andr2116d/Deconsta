/**
 * Ayudas para elegir el usuario de una asistente. Las reglas son las del backend, que vuelve a
 * comprobarlas y decide si el usuario está libre.
 */
export const MAXIMO_USUARIO = 40

/** Minúsculas, números, punto, guion bajo y guion; sin espacios ni tildes. */
export const filtrarUsuario = (valor: string) =>
  valor
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9._-]/g, '')
    .slice(0, MAXIMO_USUARIO)

export function avisoUsuario(valor: string): string | undefined {
  if (!valor) return undefined
  if (valor.length < 3) return 'Usa al menos 3 caracteres.'
  if (!/^[a-z0-9]/.test(valor) || !/[a-z0-9]$/.test(valor)) {
    return 'Empieza y termina con una letra o un número.'
  }
  return undefined
}

export const usuarioValido = (valor: string) => /^[a-z0-9][a-z0-9._-]{1,38}[a-z0-9]$/.test(valor)

const simple = (texto: string) =>
  texto
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')

/** Primer nombre y primer apellido, como lo genera el backend: «Daniela Torres Ríos» → daniela.torres. */
export function sugerirUsuario(nombres: string, apellidos: string): string {
  const nombre = simple(nombres.trim().split(/\s+/)[0] ?? '')
  const apellido = simple(apellidos.trim().split(/\s+/)[0] ?? '')
  return nombre && apellido ? `${nombre}.${apellido}`.slice(0, 36) : ''
}

export const formatearCelular = (numero: string | null) =>
  numero ? `+51 ${numero.slice(0, 3)} ${numero.slice(3, 6)} ${numero.slice(6)}` : null
