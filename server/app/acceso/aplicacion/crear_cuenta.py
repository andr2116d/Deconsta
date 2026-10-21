import secrets
import unicodedata
from dataclasses import dataclass
from uuid import uuid4

from app.acceso.dominio import politica_contrasena
from app.acceso.dominio.datos_personales import DatosPersonales, validar_cargo
from app.acceso.dominio.errores import DatosInvalidos
from app.acceso.dominio.modelos import (
    REGLA_NOMBRE_USUARIO,
    Accion,
    EventoAuditoria,
    Rol,
    Usuario,
    nombre_usuario_valido,
    normalizar_nombre_usuario,
)
from app.acceso.dominio.puertos import (
    FabricaUnidadDeTrabajo,
    ProtectorContrasenas,
    Reloj,
    UnidadDeTrabajo,
)

# Sin caracteres que se confunden al dictarlos o copiarlos (0/O, 1/l/I).
ALFABETO_TEMPORAL = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGITUD_TEMPORAL = 14


@dataclass(frozen=True)
class CuentaCreada:
    usuario: Usuario
    contrasena_temporal: str


def generar_contrasena_temporal(nombre_usuario: str) -> str:
    while True:
        candidata = "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(LONGITUD_TEMPORAL))
        if not politica_contrasena.evaluar(candidata, nombre_usuario=nombre_usuario):
            return candidata


def sugerir_nombre_usuario(nombres: str, apellidos: str) -> str:
    """Primer nombre y primer apellido sin tildes: 'Valentina Ramos Díaz' → valentina.ramos."""

    def simple(texto: str) -> str:
        sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
        return "".join(c for c in sin_tildes.lower() if c.isalnum())

    return f"{simple(nombres.split()[0])}.{simple(apellidos.split()[0])}"[:36]


def elegir_nombre_usuario(
    uow: UnidadDeTrabajo, solicitado: str | None, datos: DatosPersonales
) -> str:
    """El usuario pedido (validado y libre) o uno generado a partir del nombre."""
    if solicitado:
        nombre = normalizar_nombre_usuario(solicitado)
        if not nombre_usuario_valido(nombre):
            raise DatosInvalidos(campos={"nombre_usuario": REGLA_NOMBRE_USUARIO})
        if uow.usuarios.existe_nombre_usuario(nombre):
            raise DatosInvalidos(campos={"nombre_usuario": "Ese usuario ya está en uso."})
        return nombre
    base = sugerir_nombre_usuario(datos.nombres, datos.apellidos)
    nombre, sufijo = base, 1
    while uow.usuarios.existe_nombre_usuario(nombre):
        sufijo += 1
        nombre = f"{base}{sufijo}"
    return nombre


class CrearCuenta:
    """Alta de cuentas desde la línea de comandos. La cuenta empieza con una contraseña temporal y
    el indicador de cambio pendiente. El cargo lo fija quien crea la cuenta."""

    def __init__(
        self, unidad: FabricaUnidadDeTrabajo, contrasenas: ProtectorContrasenas, reloj: Reloj
    ) -> None:
        self._unidad = unidad
        self._contrasenas = contrasenas
        self._reloj = reloj

    def ejecutar(
        self,
        *,
        rol: Rol,
        datos: DatosPersonales,
        gerente_nombre_usuario: str | None = None,
        nombre_usuario: str | None = None,
        cargo: str | None = None,
    ) -> CuentaCreada:
        cargo = validar_cargo(cargo)
        with self._unidad() as uow:
            gerente_id = None
            if rol is Rol.ASISTENTE:
                gerente = uow.usuarios.por_nombre_usuario(
                    normalizar_nombre_usuario(gerente_nombre_usuario or ""), bloquear=False
                )
                if gerente is None or gerente.rol is not Rol.GERENTE:
                    raise DatosInvalidos(
                        campos={"gerente": "No existe un gerente con ese usuario."}
                    )
                gerente_id = gerente.id

            nombre = elegir_nombre_usuario(uow, nombre_usuario, datos)
            contrasena = generar_contrasena_temporal(nombre)
            ahora = self._reloj()
            usuario = Usuario(
                id=uuid4(),
                rol=rol,
                gerente_id=gerente_id,
                nombre_usuario=nombre,
                nombres=datos.nombres,
                contrasena_hash=self._contrasenas.generar_hash(contrasena),
                debe_cambiar_contrasena=True,
                contrasena_actualizada_en=ahora,
                ultimo_ingreso_en=None,
                intentos_fallidos=0,
                bloqueada_en=None,
                # Quien la crea por comando ya registra todos sus datos, correo incluido.
                datos_confirmados_en=ahora,
            )
            uow.usuarios.agregar(usuario, datos, cargo=cargo)
            uow.auditoria.registrar(
                EventoAuditoria(
                    Accion.CUENTA_CREADA,
                    cuenta_id=usuario.id,
                    detalle={"rol": rol.value, "origen": "linea_de_comandos"},
                )
            )
        return CuentaCreada(usuario, contrasena)
