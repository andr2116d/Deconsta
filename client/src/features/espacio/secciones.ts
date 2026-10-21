import type { Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'

import type { Rol } from '@/features/acceso/types'
import type { NombreIcono } from '@/shared/components/iconos'

/** Dónde aparece la sección dentro del espacio. */
export type Ubicacion = 'pestana' | 'accion' | 'avisos' | 'cuenta'

type PorRol<T> = T | Record<Rol, T>

export interface Seccion {
  /** Nombre de la ruta. */
  nombre: string
  ruta: string
  etiqueta: PorRol<string>
  /** Qué se podrá hacer en la sección cuando esté disponible. */
  descripcion: PorRol<string>
  icono: NombreIcono
  ubicacion: Ubicacion
  roles: readonly Rol[]
  /** Pantalla ya construida. Sin ella, la sección muestra que está en desarrollo. */
  vista?: () => Promise<Component>
  /** Pestaña dentro de «Mi cuenta», con su nombre corto. */
  pestanaCuenta?: string
}

const RUTA_CUENTA = 'cuenta'

const AMBOS: readonly Rol[] = ['gerente', 'asistente']

/**
 * Secciones del espacio de trabajo. De aquí salen las rutas, las pestañas y el menú de la cuenta.
 * Ocultar una sección a un rol solo ordena la interfaz: el backend autoriza cada operación.
 */
export const SECCIONES: readonly Seccion[] = [
  {
    nombre: 'inicio',
    ruta: 'inicio',
    etiqueta: { gerente: 'Resumen', asistente: 'Mi jornada' },
    descripcion: {
      gerente: 'Lo que vence pronto, lo que espera tu decisión y lo pagado en el mes, en soles.',
      asistente: 'Tus encargos del día, ordenados por prioridad y fecha de vencimiento.',
    },
    icono: 'inicio',
    ubicacion: 'pestana',
    roles: AMBOS,
  },
  {
    nombre: 'por-autorizar',
    ruta: 'por-autorizar',
    etiqueta: 'Por autorizar',
    descripcion:
      'Las deudas que superan tu límite o tienen otro titular esperarán aquí tu autorización, o su devolución con un motivo.',
    icono: 'escudo',
    ubicacion: 'pestana',
    roles: ['gerente'],
  },
  {
    nombre: 'por-verificar',
    ruta: 'por-verificar',
    etiqueta: 'Por verificar',
    descripcion:
      'Los comprobantes que adjunte tu asistente, para confirmar cada pago o devolverlo con una observación.',
    icono: 'check',
    ubicacion: 'pestana',
    roles: ['gerente'],
  },
  {
    nombre: 'pagos-por-completar',
    ruta: 'pagos-por-completar',
    etiqueta: 'Pagos por completar',
    descripcion: 'Los pagos que te asignaron, con su vencimiento y el comprobante por adjuntar.',
    icono: 'reloj',
    ubicacion: 'pestana',
    roles: ['asistente'],
  },
  {
    nombre: 'mis-registros',
    ruta: 'mis-registros',
    etiqueta: 'Mis registros',
    descripcion: 'Las deudas que registraste, su estado y las correcciones que te pidan.',
    icono: 'documento',
    ubicacion: 'pestana',
    roles: ['asistente'],
  },
  {
    nombre: 'calendario',
    ruta: 'calendario',
    etiqueta: 'Calendario',
    descripcion: 'Los vencimientos del mes, día por día, con el detalle de cada deuda.',
    icono: 'calendario',
    ubicacion: 'pestana',
    roles: AMBOS,
  },
  {
    nombre: 'historial',
    ruta: 'historial',
    etiqueta: 'Historial',
    descripcion: 'Cada deuda y cada pago, con quién hizo qué, cuándo y por qué.',
    icono: 'reloj',
    ubicacion: 'pestana',
    roles: ['gerente'],
  },
  {
    nombre: 'equipo',
    ruta: 'equipo',
    etiqueta: 'Mi equipo',
    descripcion: 'Las cuentas de tus asistentes: crearlas, desbloquearlas y ver sus encargos.',
    icono: 'equipo',
    ubicacion: 'pestana',
    roles: ['gerente'],
  },
  {
    nombre: 'registrar-deuda',
    ruta: 'registrar-deuda',
    etiqueta: 'Registrar deuda',
    descripcion:
      'Registrarás una deuda con su documento, el importe en soles y su fecha de vencimiento.',
    icono: 'mas',
    ubicacion: 'accion',
    roles: AMBOS,
  },
  {
    nombre: 'notificaciones',
    ruta: 'notificaciones',
    etiqueta: 'Notificaciones',
    descripcion:
      'Cada aviso de tu cuenta con su siguiente paso. Se conservarán aunque cierres sesión.',
    icono: 'avisos',
    ubicacion: 'avisos',
    roles: AMBOS,
  },
  {
    nombre: 'mis-datos',
    ruta: RUTA_CUENTA,
    etiqueta: 'Mis datos personales',
    descripcion: 'Tus nombres, tu correo, tu teléfono y tu documento, para mantenerlos al día.',
    icono: 'persona',
    ubicacion: 'cuenta',
    roles: AMBOS,
    vista: () => import('@/features/cuenta/views/DatosPersonalesView.vue'),
    pestanaCuenta: 'Mis datos',
  },
  {
    nombre: 'acceso-cuenta',
    ruta: `${RUTA_CUENTA}/acceso`,
    etiqueta: 'Usuario y contraseña',
    descripcion: 'Tu usuario de acceso y tu contraseña.',
    icono: 'candado',
    ubicacion: 'cuenta',
    roles: AMBOS,
    vista: () => import('@/features/cuenta/views/AccesoCuentaView.vue'),
    pestanaCuenta: 'Usuario y contraseña',
  },
  {
    nombre: 'permisos',
    ruta: `${RUTA_CUENTA}/permisos`,
    etiqueta: 'Mi rol y permisos',
    descripcion: 'Qué puede hacer tu rol y qué le corresponde al otro.',
    icono: 'escudo',
    ubicacion: 'cuenta',
    roles: AMBOS,
    vista: () => import('@/features/cuenta/views/PermisosView.vue'),
    pestanaCuenta: 'Mi rol y permisos',
  },
  {
    nombre: 'privacidad',
    ruta: `${RUTA_CUENTA}/privacidad`,
    etiqueta: 'Privacidad y autorizaciones',
    descripcion: 'Los términos y la política que aceptaste, con su versión y su fecha.',
    icono: 'documento',
    ubicacion: 'cuenta',
    roles: AMBOS,
    vista: () => import('@/features/cuenta/views/PrivacidadView.vue'),
    pestanaCuenta: 'Privacidad',
  },
  {
    nombre: 'configuracion',
    ruta: 'configuracion',
    etiqueta: 'Límites y categorías',
    descripcion:
      'El importe a partir del cual una deuda necesita tu autorización y las categorías de tu espacio.',
    icono: 'configuracion',
    ubicacion: 'cuenta',
    roles: ['gerente'],
  },
]

export function textoPorRol(texto: PorRol<string>, rol: Rol): string {
  return typeof texto === 'string' ? texto : texto[rol]
}

export function seccionesDe(rol: Rol, ubicacion: Ubicacion): Seccion[] {
  return SECCIONES.filter((s) => s.ubicacion === ubicacion && s.roles.includes(rol))
}

export function seccion(nombre: string): Seccion {
  const encontrada = SECCIONES.find((s) => s.nombre === nombre)
  if (!encontrada) throw new Error(`Sección desconocida: ${nombre}`)
  return encontrada
}

export const pestanasCuenta = () => SECCIONES.filter((s) => s.pestanaCuenta)

function rutaDe(s: Seccion, ruta = s.ruta): RouteRecordRaw {
  return {
    path: ruta,
    name: s.nombre,
    component: s.vista ?? (() => import('./views/EnDesarrolloView.vue')),
    meta: {
      titulo: textoPorRol(s.etiqueta, 'gerente'),
      seccion: s,
      roles: s.roles,
    },
  }
}

/**
 * Rutas hijas del espacio. Las pestañas de «Mi cuenta» cuelgan de una ruta padre con su propio
 * marco, así cambiar de pestaña no rehace la página. Las secciones sin pantalla dicen que están
 * en desarrollo.
 */
export function rutasDelEspacio(): RouteRecordRaw[] {
  const prefijo = `${RUTA_CUENTA}/`
  return [
    ...SECCIONES.filter((s) => !s.pestanaCuenta).map((s) => rutaDe(s)),
    {
      path: RUTA_CUENTA,
      component: () => import('@/features/cuenta/layouts/CuentaLayout.vue'),
      children: pestanasCuenta().map((s) =>
        rutaDe(s, s.ruta.startsWith(prefijo) ? s.ruta.slice(prefijo.length) : ''),
      ),
    },
  ]
}
