import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueJsx(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Siempre el mismo puerto: si está ocupado (otro Vite viejo), falla en vez de mudarse a otro y
    // dejar la pantalla apuntando a lo que ya corría.
    port: 5173,
    strictPort: true,
    // La API se sirve en el mismo origen que la SPA: la cookie de sesión es SameSite=Strict y
    // en producción el proxy (Caddy) cumple el mismo papel. vite preview hereda este proxy.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY ?? 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
})
