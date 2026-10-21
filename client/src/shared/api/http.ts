/**
 * Cliente HTTP de la API. Envía la cookie de sesión del mismo origen y convierte cualquier
 * respuesta de error en un ErrorApi con el código estable que define el backend.
 */

export interface CuerpoError {
  code: string
  detail: string
  fields?: Record<string, string>
  retry_after?: number
  reference?: string
}

export class ErrorApi extends Error {
  readonly estado: number
  readonly codigo: string
  readonly campos: Record<string, string>
  readonly reintentarEn: number | null
  readonly referencia: string | null

  constructor(estado: number, cuerpo: CuerpoError) {
    super(cuerpo.detail)
    this.name = 'ErrorApi'
    this.estado = estado
    this.codigo = cuerpo.code
    this.campos = cuerpo.fields ?? {}
    this.reintentarEn = cuerpo.retry_after ?? null
    this.referencia = cuerpo.reference ?? null
  }
}

const SIN_CONEXION: CuerpoError = {
  code: 'SIN_CONEXION',
  detail: 'No pudimos conectar con Deconsta. Revisa tu conexión e inténtalo de nuevo.',
}

const RESPUESTA_INESPERADA: CuerpoError = {
  code: 'ERROR_INTERNO',
  detail: 'Ocurrió un error inesperado. Inténtalo de nuevo en unos minutos.',
}

function esCuerpoError(valor: unknown): valor is CuerpoError {
  return (
    typeof valor === 'object' &&
    valor !== null &&
    typeof (valor as CuerpoError).code === 'string' &&
    typeof (valor as CuerpoError).detail === 'string'
  )
}

export async function solicitar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(`/api/v1${ruta}`, {
      ...opciones,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', ...opciones.headers },
    })
  } catch {
    throw new ErrorApi(0, SIN_CONEXION)
  }

  if (respuesta.status === 204) return undefined as T

  const cuerpo: unknown = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, esCuerpoError(cuerpo) ? cuerpo : RESPUESTA_INESPERADA)
  }
  return cuerpo as T
}

export function enviarJson<T>(ruta: string, datos?: unknown): Promise<T> {
  return solicitar<T>(ruta, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  })
}
