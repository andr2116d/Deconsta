from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.acceso.infraestructura.http.esquemas import enmascarar, exigir
from app.core.esquemas import Entrada
from app.reglas.aplicacion.reglas import DocumentoPorEvaluar, NuevoTitular, ReglasDelEspacio
from app.reglas.dominio.evaluacion import Evaluacion, MotivoAutorizacion
from app.reglas.dominio.titulares import MAXIMO_TITULARES, TipoDocumentoTitular, TitularAutorizado


class LimiteEntrada(Entrada):
    # Texto («2900.50»), nunca float: los céntimos se conservan exactos. null quita el límite.
    limite_importe: str | None = Field(..., max_length=20)

    @field_validator("limite_importe")
    @classmethod
    def validar_limite(cls, valor: str | None) -> str | None:
        return None if valor is None else exigir(valor, "Escribe el límite en soles.")


class TitularEntrada(Entrada):
    # Los topes son holgados: el dominio da el mensaje preciso de cada regla.
    nombre: str = Field("", max_length=300, validate_default=True)
    tipo_documento: str | None = Field(None, max_length=10)
    numero_documento: str | None = Field(None, max_length=30)
    relacion: str | None = Field(None, max_length=100)
    autorizacion_declarada: bool = False

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        return exigir(valor, "Escribe el nombre como aparece en sus recibos.")

    def nuevo(self) -> NuevoTitular:
        return NuevoTitular(
            self.nombre,
            self.tipo_documento or None,
            self.numero_documento or None,
            self.relacion,
            self.autorizacion_declarada,
        )


class EdicionTitularEntrada(Entrada):
    nombre: str = Field("", max_length=300, validate_default=True)
    relacion: str | None = Field(None, max_length=100)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        return exigir(valor, "Escribe el nombre como aparece en sus recibos.")


class EvaluacionEntrada(Entrada):
    importe: str = Field("", max_length=20, validate_default=True)
    titular_nombre: str | None = Field(None, max_length=300)
    titular_tipo_documento: str | None = Field(None, max_length=10)
    titular_numero_documento: str | None = Field(None, max_length=30)

    @field_validator("importe")
    @classmethod
    def validar_importe(cls, valor: str) -> str:
        return exigir(valor, "Escribe el importe en soles.")

    def documento(self) -> DocumentoPorEvaluar:
        return DocumentoPorEvaluar(
            self.importe,
            self.titular_nombre,
            self.titular_tipo_documento or None,
            self.titular_numero_documento or None,
        )


class TitularSalida(BaseModel):
    id: UUID
    nombre: str
    relacion: str | None
    tipo_documento: TipoDocumentoTitular | None
    # Enmascarado: basta para reconocerlo; el número completo no sale del servidor.
    documento: str | None
    autorizacion_declarada_en: datetime
    creado_en: datetime

    @classmethod
    def desde(cls, titular: TitularAutorizado) -> "TitularSalida":
        documento = titular.documento
        return cls(
            id=titular.id,
            nombre=titular.nombre,
            relacion=titular.relacion,
            tipo_documento=documento.tipo if documento else None,
            documento=enmascarar(documento.numero) if documento else None,
            autorizacion_declarada_en=titular.autorizacion_declarada_en,
            creado_en=titular.creado_en,
        )


class ReglasSalida(BaseModel):
    # Texto con dos decimales («2900.00»); null: sin límite.
    limite_importe: str | None
    actualizado_en: datetime | None
    titulares: list[TitularSalida]
    maximo_titulares: int = MAXIMO_TITULARES

    @classmethod
    def desde(cls, reglas: ReglasDelEspacio) -> "ReglasSalida":
        regla = reglas.regla
        limite = regla.limite_importe if regla else None
        return cls(
            limite_importe=f"{limite:.2f}" if limite is not None else None,
            actualizado_en=regla.actualizado_en if regla else None,
            titulares=[TitularSalida.desde(t) for t in reglas.titulares],
        )


class MotivoSalida(BaseModel):
    codigo: MotivoAutorizacion
    detalle: str


class EvaluacionSalida(BaseModel):
    requiere_autorizacion: bool
    motivos: list[MotivoSalida]
    titular_reconocido: str | None

    @classmethod
    def desde(cls, evaluacion: Evaluacion) -> "EvaluacionSalida":
        return cls(
            requiere_autorizacion=evaluacion.requiere_autorizacion,
            motivos=[MotivoSalida(codigo=m.codigo, detalle=m.detalle) for m in evaluacion.motivos],
            titular_reconocido=evaluacion.titular_reconocido,
        )
