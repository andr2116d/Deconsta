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
  destello: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z',
} as const

export type NombreIcono = keyof typeof trazos
