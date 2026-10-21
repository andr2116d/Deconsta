// Trazos de 24×24 de la identidad (DECONSTA/assets/product.js).
export const trazos = {
  avisos: 'M18 8a6 6 0 0 0-12 0c0 6-3 6-3 9h18c0-3-3-3-3-9M10 21h4',
  calendario: 'M4 5h16v16H4ZM8 3v4M16 3v4M4 10h16',
  candado: 'M6 10h12v11H6ZM8 10V7a4 4 0 0 1 8 0v3',
  check: 'm5 12 4 4L19 6',
  configuracion:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4',
  derecha: 'm10 6 6 6-6 6',
  documento: 'M6 3h8l4 4v14H6ZM14 3v5h4M9 12h6M9 16h4',
  equipo:
    'M9 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6M3 21v-5a6 6 0 0 1 12 0v5M16 4a3 3 0 0 1 0 6M18 14a4 4 0 0 1 3 4v3',
  escudo: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6ZM8 12l3 3 5-5',
  inicio: 'm3 10 9-7 9 7v10h-6v-6H9v6H3Z',
  mas: 'M12 5v14M5 12h14',
  persona: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2',
  reloj: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v5l3 2',
  salir: 'M10 3H4v18h6M10 12h11m-5-5 5 5-5 5',
  abajo: 'm6 9 6 6 6-6',
  alerta:
    'M12 8v5m0 3h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  cerrar: 'M6 6l12 12M18 6 6 18',
  destello: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z',
  lapiz: 'M4 20h4L19 9l-4-4L4 16ZM13.5 6.5l4 4',
  archivo: 'M3 4h18v4H3ZM5 8v12h14V8M10 12h4',
  // Categorías de gasto.
  agua: 'M12 3s-6 6.6-6 11a6 6 0 0 0 12 0c0-4.4-6-11-6-11Z',
  luz: 'M13 2 4 14h7l-1 8 9-12h-7Z',
  gas: 'M12 3c.5 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-4 2.5-5 .3 1.5 1 2.5 2 3 1-2.5.5-5.5.5-8Z',
  telefono: 'M7 2h10v20H7ZM11 18h2',
  internet: 'M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19.5h.01',
  tarjeta: 'M2 6h20v12H2ZM2 10h20M6 15h4',
  banco: 'M3 10 12 4l9 6ZM5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18',
  impuestos: 'M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2ZM9 8h6M9 12h6M9 16h3',
  vivienda: 'M3 11 12 4l9 7M5 10v11h14V10M10 21v-6h4v6',
  transporte: 'M3 16v-4l2.5-5h13l2.5 5v4ZM3 12h18M6 16v3M18 16v3M7 14h.01M17 14h.01',
  salud:
    'M12 20s-8-4.5-8-10.5A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 8 2.5C20 15.5 12 20 12 20ZM9 12h2l1-2 1 4 1-2h1',
  educacion: 'M2 9l10-5 10 5-10 5ZM6 11v5c3 2.5 9 2.5 12 0v-5M22 9v6',
  seguro: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z',
  etiqueta: 'M3 3h8l10 10-8 8L3 11ZM7.5 7.5h.01',
} as const

export type NombreIcono = keyof typeof trazos
