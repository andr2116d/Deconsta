"""Alta de cuentas desde la terminal. Imprime el usuario y una contraseña temporal una sola vez; la
cuenta deberá cambiarla al ingresar.

    uv run python -m app.acceso.infraestructura.cli crear-gerente --nombres "Valentina" \\
        --apellidos "Ramos Díaz" --correo valentina@ejemplo.pe --tipo-documento dni \\
        --numero-documento 45678912 [--telefono 987654321] [--usuario valentina.ramos]

    uv run python -m app.acceso.infraestructura.cli crear-asistente --gerente valentina.ramos ...
"""

import argparse
import sys

from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import ErrorAcceso
from app.acceso.dominio.modelos import Rol
from app.contenedor import Contenedor
from app.core.config import settings
from app.core.migraciones import ErrorMigracion, aplicar_pendientes


def analizador() -> argparse.ArgumentParser:
    principal = argparse.ArgumentParser(prog="cli", description="Alta de cuentas de Deconsta")
    ordenes = principal.add_subparsers(dest="orden", required=True)
    for orden in ("crear-gerente", "crear-asistente"):
        sub = ordenes.add_parser(orden)
        if orden == "crear-asistente":
            sub.add_argument("--gerente", required=True, help="Usuario del gerente responsable")
        sub.add_argument("--nombres", required=True)
        sub.add_argument("--apellidos", required=True)
        sub.add_argument("--correo", required=True)
        sub.add_argument("--tipo-documento", required=True, choices=["dni", "ce"])
        sub.add_argument("--numero-documento", required=True)
        sub.add_argument("--telefono")
        sub.add_argument("--usuario", help="Si se omite, se genera a partir del nombre")
    return principal


def main(argumentos: list[str]) -> int:
    args = analizador().parse_args(argumentos)
    salida, errores = sys.stdout, sys.stderr
    try:
        aplicar_pendientes(settings.database_url)
        datos = DatosPersonales.crear(
            nombres=args.nombres,
            apellidos=args.apellidos,
            correo=args.correo,
            tipo_documento=args.tipo_documento,
            numero_documento=args.numero_documento,
            telefono=args.telefono,
        )
        contenedor = Contenedor.crear(settings)
        try:
            creada = contenedor.crear_cuenta.ejecutar(
                rol=Rol.GERENTE if args.orden == "crear-gerente" else Rol.ASISTENTE,
                datos=datos,
                gerente_nombre_usuario=getattr(args, "gerente", None),
                nombre_usuario=args.usuario,
            )
        finally:
            contenedor.cerrar()
    except ErrorMigracion as error:
        errores.write(f"{error}\n")
        return 1
    except ErrorAcceso as error:
        detalle = "; ".join(f"{campo}: {mensaje}" for campo, mensaje in error.campos.items())
        errores.write(f"{error.mensaje} {detalle}\n")
        return 1
    salida.write(
        f"Cuenta de {creada.usuario.rol.value} creada.\n"
        f"Id: {creada.usuario.id}\n"
        f"Usuario: {creada.usuario.nombre_usuario}\n"
        f"Contraseña temporal: {creada.contrasena_temporal}\n"
        "Compártela por un canal seguro; se pedirá cambiarla al ingresar.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
