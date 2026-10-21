"""Evaluación de un documento contra las reglas del espacio.

Es la regla que aplicará el registro de deudas: lo que registra una asistente espera la
autorización del gerente si su importe es mayor que el límite o si el titular no es el gerente ni
uno de sus titulares autorizados. Lo que registra el propio gerente no espera a nadie: un titular
distinto solo se le avisa.

Un documento sin titular legible (por ejemplo, una boleta de menos de S/ 700, que no identifica al
comprador) no se marca como de otro titular: no hay con qué compararlo.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.acceso.dominio.modelos import Rol
from app.reglas.dominio.importes import formatear_soles
from app.reglas.dominio.titulares import Documento, nombres_coinciden


class MotivoAutorizacion(StrEnum):
    IMPORTE_SOBRE_LIMITE = "IMPORTE_SOBRE_LIMITE"
    TITULAR_DISTINTO = "TITULAR_DISTINTO"


@dataclass(frozen=True)
class Identidad:
    """Alguien cuyos recibos no piden autorización por titular: el gerente o un titular
    autorizado. `etiqueta` dice quién es sin repetir su documento."""

    nombres: tuple[str, ...]
    documento: Documento | None
    etiqueta: str

    def reconoce(self, nombre: str | None, documento: Documento | None) -> bool:
        if documento and self.documento:
            # Dos documentos distintos son dos personas, aunque el nombre coincida.
            return self.documento.coincide(documento)
        return bool(nombre) and any(nombres_coinciden(nombre or "", n) for n in self.nombres)


@dataclass(frozen=True)
class TitularDelDocumento:
    nombre: str | None = None
    documento: Documento | None = None

    @property
    def legible(self) -> bool:
        return bool(self.nombre or self.documento)


@dataclass(frozen=True)
class Motivo:
    codigo: MotivoAutorizacion
    detalle: str


@dataclass(frozen=True)
class Evaluacion:
    # Lo que hace esperar la autorización del gerente.
    motivos: tuple[Motivo, ...] = ()
    # Lo que solo se advierte (al gerente, que no se autoriza a sí mismo).
    avisos: tuple[Motivo, ...] = ()
    # Quién se reconoció como titular, si alguien.
    titular_reconocido: str | None = None

    @property
    def requiere_autorizacion(self) -> bool:
        return bool(self.motivos)


def evaluar(
    *,
    registra: Rol,
    importe: Decimal,
    limite: Decimal | None,
    titular: TitularDelDocumento,
    identidades: list[Identidad],
) -> Evaluacion:
    hallazgos: list[Motivo] = []
    if limite is not None and importe > limite:
        hallazgos.append(
            Motivo(
                MotivoAutorizacion.IMPORTE_SOBRE_LIMITE,
                f"El importe de {formatear_soles(importe)} supera tu límite de "
                f"{formatear_soles(limite)}.",
            )
        )
    reconocido = next(
        (i for i in identidades if i.reconoce(titular.nombre, titular.documento)), None
    )
    if titular.legible and reconocido is None:
        hallazgos.append(
            Motivo(
                MotivoAutorizacion.TITULAR_DISTINTO,
                "El titular del documento no eres tú ni uno de tus titulares autorizados.",
            )
        )
    etiqueta = reconocido.etiqueta if reconocido else None
    if registra is Rol.GERENTE:
        avisos = tuple(m for m in hallazgos if m.codigo is MotivoAutorizacion.TITULAR_DISTINTO)
        return Evaluacion(avisos=avisos, titular_reconocido=etiqueta)
    return Evaluacion(motivos=tuple(hallazgos), titular_reconocido=etiqueta)
