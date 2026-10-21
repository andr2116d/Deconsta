import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '../api/categorias'
import type { Categoria, DatosCategoria } from '../types'

const porNombre = (a: Categoria, b: Categoria) =>
  a.nombre.localeCompare(b.nombre, 'es', { sensitivity: 'base' })

/**
 * Categorías del espacio. Cada operación actualiza la lista con lo que devuelve la API, así la
 * pantalla cambia al momento sin volver a cargar todo.
 */
export const useCategoriasStore = defineStore('categorias', () => {
  const categorias = ref<Categoria[] | null>(null)
  const cargando = ref(false)
  const errorCarga = ref<unknown>(null)

  const activas = computed(() => (categorias.value ?? []).filter((c) => !c.archivada))
  const archivadas = computed(() => (categorias.value ?? []).filter((c) => c.archivada))

  function reemplazar(categoria: Categoria): Categoria {
    const resto = (categorias.value ?? []).filter((c) => c.id !== categoria.id)
    categorias.value = [...resto, categoria].sort(porNombre)
    return categoria
  }

  async function cargar(): Promise<void> {
    cargando.value = true
    errorCarga.value = null
    try {
      categorias.value = (await api.listarCategorias()).sort(porNombre)
    } catch (error) {
      errorCarga.value = error
      throw error
    } finally {
      cargando.value = false
    }
  }

  const crear = async (datos: DatosCategoria) => reemplazar(await api.crearCategoria(datos))

  const editar = async (id: string, datos: DatosCategoria) =>
    reemplazar(await api.editarCategoria(id, datos))

  const archivar = async (id: string, motivo: string | null) =>
    reemplazar(await api.archivarCategoria(id, motivo))

  const reactivar = async (id: string) => reemplazar(await api.reactivarCategoria(id))

  /** Al cambiar de cuenta no quedan datos de otro espacio en memoria. */
  function olvidar(): void {
    categorias.value = null
  }

  return {
    categorias,
    activas,
    archivadas,
    cargando,
    errorCarga,
    cargar,
    crear,
    editar,
    archivar,
    reactivar,
    olvidar,
  }
})
