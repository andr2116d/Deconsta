import type { Cuenta } from '../types'

export const CUENTA: Cuenta = {
  id: '1',
  rol: 'gerente',
  nombre_usuario: 'valentina.ramos',
  nombres: 'Valentina',
  apellidos: 'Ramos Díaz',
  correo: 'valentina@ejemplo.pe',
  telefono: '987654321',
  tipo_documento: 'dni',
  numero_documento: '45678912',
  nombre_recibos: null,
  cargo: 'Gerente general',
  debe_cambiar_contrasena: false,
  contrasena_actualizada_en: '2026-10-21T10:00:00Z',
  cambios_nombre_usuario: {
    maximo: 3,
    usados: 0,
    restantes: 3,
    renueva_en: '2026-11-01T00:00:00-05:00',
  },
}
