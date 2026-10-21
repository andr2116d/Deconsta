"""Rutas del historial del espacio.

`GET /historial`: todo el espacio con la incorporación completa. Filtros opcionales: `desde` y
`hasta` (días del espacio, hasta 366; sin ellos, los últimos 90), `estado` (de la deuda, de alguno
de sus pagos o `mora`), `categoria_id`, `registrada_por`, `pagado_por`, `lugar_pago`, `q` (en el
concepto) y `mios` («Mis registros»: lo que la cuenta registró o pagó). Responde de la deuda más
reciente a la más antigua, `limite` por página (25, hasta 100), y `siguiente` para pedir la página
que sigue con `cursor`. La confianza de los pagos solo la ve el gerente.

`GET /historial/exportacion`: solo el gerente (403 SIN_PERMISO). Un CSV con una fila por cuota, sin
datos personales cifrados: quien registró o pagó va con su nombre de usuario.

Errores propios: 422 DATOS_INVALIDOS (rango, búsqueda o cursor).
"""

import csv
import io
from datetime import date
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Response

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.deudas.dominio.modelos import LugarPago
from app.historial.aplicacion.historial import ConsultaHistorial, Exportacion
from app.historial.dominio.modelos import EstadoFiltro
from app.historial.infraestructura.http.esquemas import HistorialSalida, leer_cursor

router = APIRouter(prefix="/historial", tags=["historial"])

COLUMNAS = (
    "registrada_el",
    "concepto",
    "categoria",
    "tipo_documento",
    "estado_deuda",
    "motivos_autorizacion",
    "cuota",
    "cuotas",
    "vence_el",
    "importe_cuota",
    "estado_pago",
    "pagado_el",
    "importe_pagado",
    "comision",
    "mora",
    "lugar_pago",
    "registrada_por",
    "pagado_por",
    "motivo_decision_deuda",
    "motivo_decision_pago",
)
# Una celda que empieza así la ejecuta una hoja de cálculo como fórmula.
INICIO_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _consulta(
    desde: date | None,
    hasta: date | None,
    estado: EstadoFiltro | None,
    categoria_id: UUID | None,
    registrada_por: UUID | None,
    pagado_por: UUID | None,
    lugar_pago: LugarPago | None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    mios: bool = False,
) -> ConsultaHistorial:
    return ConsultaHistorial(
        desde, hasta, estado, categoria_id, registrada_por, pagado_por, lugar_pago, q, mios
    )


@router.get("", responses=ERRORES)
def consultar(
    sesion: SesionHabilitadaDep,
    contenedor: ContenedorDep,
    desde: date | None = None,
    hasta: date | None = None,
    estado: EstadoFiltro | None = None,
    categoria_id: UUID | None = None,
    registrada_por: UUID | None = None,
    pagado_por: UUID | None = None,
    lugar_pago: LugarPago | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    mios: bool = False,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 25,
) -> HistorialSalida:
    consulta = _consulta(
        desde, hasta, estado, categoria_id, registrada_por, pagado_por, lugar_pago, q, mios
    )
    pagina = contenedor.consultar_historial.ejecutar(
        sesion, consulta, leer_cursor(cursor) if cursor else None, limite
    )
    return HistorialSalida.desde_pagina(pagina)


def _celda(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    return f"'{texto}" if texto.startswith(INICIO_FORMULA) else texto


def _csv(exportacion: Exportacion, zona: ZoneInfo) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS)
    usuarios, categorias = exportacion.usuarios, exportacion.categorias
    for deuda in exportacion.deudas:
        for cuota in deuda.cuotas:
            # El pago vigente o, si no hay, el último devuelto.
            pago = deuda.pago_vigente(cuota.numero) or next(
                (p for p in reversed(deuda.pagos) if p.cuota == cuota.numero), None
            )
            fila = (
                deuda.creado_en.astimezone(zona).date().isoformat(),
                deuda.concepto,
                categorias.get(deuda.categoria_id, "Otros") if deuda.categoria_id else "Otros",
                deuda.tipo_documento.value,
                deuda.estado.value,
                " ".join(deuda.motivos),
                cuota.numero,
                len(deuda.cuotas),
                cuota.vence_el.isoformat(),
                cuota.importe,
                pago.estado.value if pago else "",
                pago.pagado_el.isoformat() if pago else "",
                pago.importe if pago else "",
                pago.comision if pago else "",
                pago.mora if pago else "",
                pago.lugar_pago.value if pago and pago.lugar_pago else "",
                usuarios.get(deuda.registrada_por, ""),
                usuarios.get(pago.registrado_por, "") if pago else "",
                deuda.motivo_decision,
                pago.motivo_decision if pago else "",
            )
            escritor.writerow([_celda(valor) for valor in fila])
    return salida.getvalue()


@router.get("/exportacion", responses=ERRORES, response_class=Response)
def exportar(
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    desde: date | None = None,
    hasta: date | None = None,
    estado: EstadoFiltro | None = None,
    categoria_id: UUID | None = None,
    registrada_por: UUID | None = None,
    pagado_por: UUID | None = None,
    lugar_pago: LugarPago | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Response:
    consulta = _consulta(
        desde, hasta, estado, categoria_id, registrada_por, pagado_por, lugar_pago, q
    )
    exportacion = contenedor.exportar_historial.ejecutar(sesion, consulta)
    filtros = exportacion.filtros
    nombre = f"historial-{filtros.desde.isoformat()}-a-{filtros.hasta.isoformat()}.csv"
    encabezados = {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "Cache-Control": "no-store",
    }
    if exportacion.incompleta:
        encabezados["X-Historial-Incompleto"] = "true"
    # Con BOM, Excel abre las tildes bien.
    contenido = "﻿" + _csv(exportacion, ZoneInfo(contenedor.config.timezone))
    return Response(contenido, media_type="text/csv; charset=utf-8", headers=encabezados)
