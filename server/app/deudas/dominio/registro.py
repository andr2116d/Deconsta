"""Reglas del registro de una deuda.

Lo que se envía al registrar se valida aquí: concepto, cuotas en soles, lugar de pago, titular y
código de pago. Las reglas del espacio (límite y titulares) se aplican con lo que dice el
documento, no con lo que se corrigió a mano: si la asistente baja el importe o cambia el titular,
la regla sigue viendo el del documento. Lo corregido queda anotado para el gerente.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.acceso.dominio.modelos import Rol
from app.deudas.dominio.errores import DeudaInvalida
from app.deudas.dominio.modelos import Cuota, LugarPago, MotivoEspera
from app.documentos.dominio.analisis import normalizar_numero
from app.documentos.dominio.modelos import Analisis, DatosLeidos, Riesgo
from app.reglas.dominio.evaluacion import (
    Evaluacion,
    Identidad,
    MotivoAutorizacion,
    TitularDelDocumento,
    evaluar,
)
from app.reglas.dominio.importes import IMPORTE_MAXIMO, a_importe, error_importe, formatear_soles
from app.reglas.dominio.titulares import Documento, clave_nombre, documento_de, limpiar

LARGO_CONCEPTO = (2, 80)
LARGO_TITULAR = (3, 120)
LARGO_CODIGO = 40
MAXIMO_CUOTAS = 360
# Una deuda vencida también se registra (se acumularon); no una de hace años ni a décadas.
ANTIGUEDAD_MAXIMA = timedelta(days=730)
PLAZO_MAXIMO = timedelta(days=365 * 30)
PATRON_CONCEPTO = re.compile(r"^[^\W_][\w .,&'’()/#°º:+-]*$")
PATRON_CODIGO = re.compile(r"^[0-9A-Za-z][0-9A-Za-z -]*$")

LUGARES = {lugar.value for lugar in LugarPago}


@dataclass(frozen=True)
class CuotaEnviada:
    vence_el: date | None
    importe: str


@dataclass(frozen=True)
class DatosDeuda:
    concepto: str
    lugar_pago: LugarPago
    cuotas: tuple[Cuota, ...]
    titular_nombre: str | None
    titular_documento: Documento | None
    codigo_pago: str | None

    @property
    def importe(self) -> Decimal:
        return sum((c.importe for c in self.cuotas), Decimal("0"))

    @classmethod
    def crear(
        cls,
        *,
        concepto: str,
        lugar_pago: str | None,
        cuotas: list[CuotaEnviada],
        titular_nombre: str | None,
        titular_tipo_documento: str | None,
        titular_numero_documento: str | None,
        codigo_pago: str | None,
        hoy: date,
    ) -> "DatosDeuda":
        errores: dict[str, str] = {}
        concepto = limpiar(concepto)
        minimo, maximo = LARGO_CONCEPTO
        if not concepto:
            errores["concepto"] = "Escribe un nombre para la deuda, por ejemplo «Luz de la casa»."
        elif not minimo <= len(concepto) <= maximo or not PATRON_CONCEPTO.match(concepto):
            errores["concepto"] = (
                f"Usa de {minimo} a {maximo} letras, números, espacios y signos comunes."
            )
        lugar = None
        if not lugar_pago:
            errores["lugar_pago"] = "Elige dónde se pagará esta deuda."
        elif lugar_pago not in LUGARES:
            errores["lugar_pago"] = "Elige uno de los lugares de pago de la lista."
        else:
            lugar = LugarPago(lugar_pago)
        validadas = _cuotas(cuotas, hoy, errores)
        nombre = limpiar(titular_nombre or "") or None
        if nombre and not LARGO_TITULAR[0] <= len(nombre) <= LARGO_TITULAR[1]:
            errores["titular_nombre"] = (
                f"Escribe el titular como figura en el documento, de {LARGO_TITULAR[0]} a "
                f"{LARGO_TITULAR[1]} caracteres."
            )
        errores_documento: dict[str, str] = {}
        documento = documento_de(
            titular_tipo_documento, titular_numero_documento, errores_documento
        )
        for campo, mensaje in errores_documento.items():
            errores[f"titular_{campo}"] = mensaje
        codigo = " ".join((codigo_pago or "").split()) or None
        if codigo and (len(codigo) > LARGO_CODIGO or not PATRON_CODIGO.match(codigo)):
            errores["codigo_pago"] = (
                f"Usa hasta {LARGO_CODIGO} letras, números, espacios o guiones, como en el "
                "documento."
            )
        if errores or lugar is None:
            raise DeudaInvalida(campos=errores)
        return cls(concepto, lugar, validadas, nombre, documento, codigo)


def _cuotas(cuotas: list[CuotaEnviada], hoy: date, errores: dict[str, str]) -> tuple[Cuota, ...]:
    if not cuotas:
        errores["cuotas"] = "Indica el importe y el vencimiento de la deuda."
        return ()
    if len(cuotas) > MAXIMO_CUOTAS:
        errores["cuotas"] = f"Una deuda puede tener hasta {MAXIMO_CUOTAS} cuotas."
        return ()
    validadas: list[Cuota] = []
    for indice, cuota in enumerate(cuotas):
        prefijo = f"cuotas.{indice}"
        if mensaje := error_importe(cuota.importe):
            errores[f"{prefijo}.importe"] = mensaje
        if cuota.vence_el is None:
            errores[f"{prefijo}.vence_el"] = "Indica la fecha de vencimiento."
        elif not hoy - ANTIGUEDAD_MAXIMA <= cuota.vence_el <= hoy + PLAZO_MAXIMO:
            errores[f"{prefijo}.vence_el"] = (
                "Revisa la fecha: no puede ser de hace más de dos años ni de dentro de más de "
                "treinta."
            )
        elif validadas and cuota.vence_el < validadas[-1].vence_el:
            errores[f"{prefijo}.vence_el"] = "Cada cuota debe vencer después de la anterior."
        if not any(clave.startswith(prefijo) for clave in errores):
            assert cuota.vence_el is not None
            validadas.append(Cuota(indice + 1, cuota.vence_el, a_importe(cuota.importe)))
    total = sum((c.importe for c in validadas), Decimal("0"))
    if len(validadas) == len(cuotas) and total > IMPORTE_MAXIMO:
        errores["cuotas"] = f"El total no puede superar {formatear_soles(IMPORTE_MAXIMO)}."
    return tuple(validadas)


def _mismo_titular(datos: DatosDeuda, leidos: DatosLeidos) -> bool:
    if leidos.titular_nombre and datos.titular_nombre:
        if clave_nombre(leidos.titular_nombre) != clave_nombre(datos.titular_nombre):
            return False
    elif bool(leidos.titular_nombre) != bool(datos.titular_nombre):
        return False
    numero_leido = normalizar_numero(leidos.titular_numero_documento)
    numero_enviado = normalizar_numero(
        datos.titular_documento.numero if datos.titular_documento else ""
    )
    return numero_leido == numero_enviado


def campos_corregidos(datos: DatosDeuda, leidos: DatosLeidos | None) -> tuple[str, ...]:
    """Qué se cambió a mano respecto de lo leído en el documento. Sin lectura, nada que comparar."""
    if leidos is None:
        return ()
    corregidos = []
    importes_leidos = [c.importe for c in leidos.cuotas] or (
        [leidos.importe] if leidos.importe else []
    )
    if importes_leidos and [c.importe for c in datos.cuotas] != importes_leidos:
        corregidos.append("importe")
    vencimientos_leidos = [c.vence_el for c in leidos.cuotas] or (
        [leidos.vence_el] if leidos.vence_el else []
    )
    if vencimientos_leidos and [c.vence_el for c in datos.cuotas] != vencimientos_leidos:
        corregidos.append("vencimiento")
    if leidos.codigo_pago and normalizar_numero(leidos.codigo_pago) != normalizar_numero(
        datos.codigo_pago
    ):
        corregidos.append("codigo_pago")
    if (leidos.titular_nombre or leidos.titular_numero_documento) and not _mismo_titular(
        datos, leidos
    ):
        corregidos.append("titular")
    return tuple(corregidos)


def titular_para_reglas(datos: DatosDeuda, leidos: DatosLeidos | None) -> TitularDelDocumento:
    """El titular que dice el documento; si no se leyó ninguno, el que se escribió."""
    if leidos and (leidos.titular_nombre or leidos.titular_numero_documento):
        documento = documento_de(leidos.titular_tipo_documento, leidos.titular_numero_documento, {})
        return TitularDelDocumento(leidos.titular_nombre, documento)
    return TitularDelDocumento(datos.titular_nombre, datos.titular_documento)


@dataclass(frozen=True)
class Resultado:
    motivos: tuple[MotivoEspera, ...]
    # Lo que se le advierte al gerente cuando registra él mismo.
    avisos: tuple[str, ...]


def evaluar_registro(
    *,
    registra: Rol,
    datos: DatosDeuda,
    analisis: Analisis | None,
    limite: Decimal | None,
    identidades: list[Identidad],
    corregidos: tuple[str, ...],
) -> Resultado:
    leidos = analisis.datos if analisis else None
    # El mayor entre lo registrado y lo leído: bajar el importe a mano no evita el límite.
    importe_leido = (leidos.importe if leidos else None) or Decimal("0")
    importe = max(datos.importe, importe_leido)
    evaluacion: Evaluacion = evaluar(
        registra=registra,
        importe=importe,
        limite=limite,
        titular=titular_para_reglas(datos, leidos),
        identidades=identidades,
    )
    riesgo = analisis.riesgo if analisis else Riesgo.MEDIO
    if registra is Rol.GERENTE:
        avisos = [m.detalle for m in evaluacion.avisos]
        if analisis:
            avisos.extend(
                s.detalle for s in analisis.senales if s.riesgo.nivel >= Riesgo.MEDIO.nivel
            )
        return Resultado((), tuple(avisos))
    motivos = [
        MotivoEspera.IMPORTE_SOBRE_LIMITE
        if m.codigo is MotivoAutorizacion.IMPORTE_SOBRE_LIMITE
        else MotivoEspera.TITULAR_DISTINTO
        for m in evaluacion.motivos
    ]
    if riesgo.nivel >= Riesgo.MEDIO.nivel:
        motivos.append(MotivoEspera.DOCUMENTO_DUDOSO)
    if {"importe", "codigo_pago"} & set(corregidos):
        motivos.append(MotivoEspera.DATOS_CORREGIDOS)
    return Resultado(tuple(motivos), ())
