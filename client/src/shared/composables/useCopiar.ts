import { onBeforeUnmount, ref } from 'vue'

/**
 * Copia texto al portapapeles y recuerda qué se copió durante unos segundos, para confirmarlo en
 * pantalla. Si el navegador no permite el portapapeles (por ejemplo, fuera de HTTPS), avisa del
 * fallo para que se copie a mano.
 */
export function useCopiar(duracion = 2500) {
  const copiado = ref<string | null>(null)
  const fallo = ref(false)
  let temporizador: ReturnType<typeof setTimeout> | undefined

  async function copiar(texto: string, clave: string): Promise<void> {
    fallo.value = false
    try {
      await navigator.clipboard.writeText(texto)
    } catch {
      fallo.value = true
      return
    }
    copiado.value = clave
    clearTimeout(temporizador)
    temporizador = setTimeout(() => (copiado.value = null), duracion)
  }

  onBeforeUnmount(() => clearTimeout(temporizador))

  return { copiado, fallo, copiar }
}
