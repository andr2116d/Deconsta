import type { Cuenta, DatosEditables } from './types'

/**
 * Normalización de los datos personales, igual a la del backend: un espacio de más o una
 * mayúscula en el correo no cuentan como cambio. El backend vuelve a comprobarlo al guardar.
 */
const texto = (valor: string) => valor.split(/\s+/).filter(Boolean).join(' ')
const opcional = (valor: string | null) => texto(valor ?? '') || null

export function normalizarDatos(datos: DatosEditables): DatosEditables {
  return {
    nombres: texto(datos.nombres),
    apellidos: texto(datos.apellidos),
    correo: datos.correo.trim().toLowerCase(),
    telefono: (datos.telefono ?? '').replace(/[\s()-]/g, '') || null,
    tipo_documento: datos.tipo_documento,
    numero_documento: datos.numero_documento.replace(/[\s-]/g, '').toUpperCase(),
    nombre_recibos: opcional(datos.nombre_recibos),
  }
}

export function datosDe(cuenta: Cuenta): DatosEditables {
  return {
    nombres: cuenta.nombres,
    apellidos: cuenta.apellidos,
    correo: cuenta.correo,
    telefono: cuenta.telefono,
    tipo_documento: cuenta.tipo_documento,
    numero_documento: cuenta.numero_documento,
    nombre_recibos: cuenta.nombre_recibos,
  }
}

export type CampoDatos = keyof DatosEditables

/** Campos que cambian de verdad respecto de lo guardado. */
export function camposCambiados(original: DatosEditables, actual: DatosEditables): CampoDatos[] {
  const antes = normalizarDatos(original)
  const despues = normalizarDatos(actual)
  return (Object.keys(antes) as CampoDatos[]).filter((campo) => antes[campo] !== despues[campo])
}

/** Cambiarlos permite identificar o recuperar la cuenta: se confirman con la contraseña. */
const SENSIBLES: readonly CampoDatos[] = ['correo', 'tipo_documento', 'numero_documento']

export const requiereContrasena = (campos: readonly CampoDatos[]) =>
  campos.some((campo) => SENSIBLES.includes(campo))

/** Forma canónica del usuario (como la del backend) y su regla de formato. */
export const normalizarNombreUsuario = (valor: string) =>
  valor.normalize('NFKC').trim().toLowerCase()

export const NOMBRE_USUARIO_VALIDO = /^[a-z0-9][a-z0-9._-]{1,38}[a-z0-9]$/

const fechaLarga = new Intl.DateTimeFormat('es-PE', { dateStyle: 'long', timeZone: 'America/Lima' })
const diaYMes = new Intl.DateTimeFormat('es-PE', {
  day: 'numeric',
  month: 'long',
  timeZone: 'America/Lima',
})

export const formatearFecha = (iso: string) => fechaLarga.format(new Date(iso))
export const formatearDiaYMes = (iso: string) => diaYMes.format(new Date(iso))
