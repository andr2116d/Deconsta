"""Errores de las reglas de autorización. Cada uno trae un código estable para el frontend y un
mensaje que dice qué ocurrió y qué hacer, sin repetir datos personales de terceros."""

from collections.abc import Mapping


class ErrorReglas(Exception):
    codigo = "ERROR_REGLAS"
    mensaje = "No pudimos completar la operación con las reglas."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class ReglaInvalida(ErrorReglas):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los datos marcados."


class SinCambios(ErrorReglas):
    codigo = "SIN_CAMBIOS"
    mensaje = "No hay cambios por guardar: los datos son iguales a los registrados."


class AutorizacionNoDeclarada(ErrorReglas):
    codigo = "AUTORIZACION_NO_DECLARADA"
    mensaje = "Confirma que esta persona te autorizó a registrar sus datos en Deconsta."

    def __init__(self) -> None:
        super().__init__(campos={"autorizacion_declarada": self.mensaje})


class TitularEsGerente(ErrorReglas):
    codigo = "TITULAR_ES_GERENTE"
    mensaje = (
        "Ese documento es el tuyo: tus recibos ya se reconocen con tus datos de Mi cuenta, no "
        "necesitas agregarte."
    )

    def __init__(self) -> None:
        super().__init__(campos={"numero_documento": self.mensaje})


class TitularDuplicado(ErrorReglas):
    codigo = "TITULAR_DUPLICADO"

    def __init__(self, campo: str) -> None:
        mensaje = (
            "Ya agregaste un titular con ese documento."
            if campo == "numero_documento"
            else "Ya agregaste un titular con ese nombre."
        )
        super().__init__(mensaje, campos={campo: mensaje})


class LimiteTitulares(ErrorReglas):
    codigo = "LIMITE_TITULARES"

    def __init__(self, maximo: int) -> None:
        super().__init__(
            f"Ya tienes {maximo} titulares autorizados, el máximo permitido. Quita alguno que ya "
            "no uses para agregar otro."
        )


class TitularNoEncontrado(ErrorReglas):
    codigo = "TITULAR_NO_ENCONTRADO"
    mensaje = "No encontramos ese titular entre tus titulares autorizados."
