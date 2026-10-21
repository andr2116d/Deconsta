import { watch } from 'vue'

/**
 * Borra el error de un campo en cuanto la persona lo edita: así vuelve a ver el aviso de lo que
 * falta en vez del error del envío anterior.
 */
export function useLimpiarErrores<T extends object>(
  datos: T,
  errores: Partial<Record<string, string | undefined>>,
): void {
  watch(
    () => ({ ...datos }),
    (actual, anterior) => {
      for (const campo of Object.keys(actual) as Array<keyof T & string>) {
        if (actual[campo] !== anterior[campo]) delete errores[campo]
      }
    },
  )
}
