import { execFileSync } from 'node:child_process'
import { randomInt } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const SERVER = fileURLToPath(new URL('../../server', import.meta.url))

export interface Cuenta {
  id: string
  usuario: string
  contrasena: string
}

/** Crea una cuenta nueva con el comando del backend (misma base que usa la API en desarrollo). */
export function crearCuenta(rol: 'gerente' | 'asistente', gerente?: string): Cuenta {
  const sufijo = String(randomInt(10_000_000, 99_999_999))
  const argumentos = [
    'run',
    'python',
    '-m',
    'app.acceso.infraestructura.cli',
    `crear-${rol}`,
    ...(gerente ? ['--gerente', gerente] : []),
    '--nombres',
    rol === 'gerente' ? 'Prueba' : 'Asistente',
    '--apellidos',
    'Automatizada',
    '--correo',
    `e2e.${sufijo}@ejemplo.pe`,
    '--tipo-documento',
    'dni',
    '--numero-documento',
    sufijo,
    '--usuario',
    `e2e.${rol}.${sufijo}`,
  ]
  const salida = execFileSync('uv', argumentos, { cwd: SERVER, encoding: 'utf8' })
  const id = /^Id: (\S+)$/m.exec(salida)?.[1]
  const contrasena = /^Contraseña temporal: (\S+)$/m.exec(salida)?.[1]
  if (!id || !contrasena) throw new Error('El comando no devolvió el id o la contraseña')
  return { id, usuario: `e2e.${rol}.${sufijo}`, contrasena }
}
