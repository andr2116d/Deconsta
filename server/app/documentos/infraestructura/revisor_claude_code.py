"""Revisión con IA en desarrollo, a través de Claude Code de esta PC.

Para probar la segunda capa sin una clave de la API: se ejecuta `claude -p` en modo de una sola
respuesta con la sesión de Claude Code de quien desarrolla. Recibe el documento como bloque de
imagen o PDF, las mismas instrucciones y el mismo esquema que el revisor de la API, y devuelve la
misma salida estructurada.

Solo en desarrollo: la configuración lo rechaza en producción, donde se usa ANTHROPIC_API_KEY.
Claude Code corre sin herramientas, sin MCP, sin configuración del usuario ni del proyecto y en una
carpeta vacía: el documento no puede pedirle que ejecute ni lea nada. El contenido viaja por la
entrada estándar, nunca en la línea de comandos.
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any

from pydantic import ValidationError

from app.documentos.dominio.modelos import Lectura, TipoArchivo
from app.documentos.dominio.puertos import CategoriaConocida, ErrorRevision, RevisionIa
from app.documentos.infraestructura.revisor_claude import (
    INSTRUCCIONES,
    Esfuerzo,
    RespuestaIa,
    bloque_documento,
    contexto_de,
    revision_de,
)

logger = logging.getLogger(__name__)

ESPERA_SEGUNDOS = 180
ESQUEMA = json.dumps(RespuestaIa.model_json_schema(), ensure_ascii=False)
# La sesión de Claude Code es la que autoriza; una clave en el entorno la reemplazaría.
VARIABLES_EXCLUIDAS = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}


def argumentos(comando: str, modelo: str, esfuerzo: Esfuerzo) -> list[str]:
    return [
        comando,
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        modelo,
        "--effort",
        esfuerzo,
        "--tools",
        "",
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--system-prompt",
        INSTRUCCIONES,
        "--json-schema",
        ESQUEMA,
    ]


def resultado_de(salida: str) -> dict[str, Any]:
    """El último evento `result` de la salida en líneas JSON."""
    for linea in reversed(salida.splitlines()):
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if isinstance(evento, dict) and evento.get("type") == "result":
            return evento
    raise ErrorRevision("Claude Code no devolvió un resultado")


class RevisorClaudeCode:
    def __init__(self, comando: str, modelo: str, esfuerzo: Esfuerzo) -> None:
        self._comando = comando
        self._modelo = modelo
        self._esfuerzo = esfuerzo

    def revisar(
        self,
        contenido: bytes,
        tipo: TipoArchivo,
        lectura: Lectura,
        categorias: list[CategoriaConocida],
    ) -> RevisionIa:
        mensaje = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    bloque_documento(contenido, tipo),
                    {"type": "text", "text": contexto_de(lectura, categorias)},
                ],
            },
        }
        entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES_EXCLUIDAS}
        try:
            with tempfile.TemporaryDirectory(prefix="deconsta-revision-") as carpeta:
                proceso = subprocess.run(
                    argumentos(self._comando, self._modelo, self._esfuerzo),
                    input=json.dumps(mensaje) + "\n",
                    capture_output=True,
                    text=True,
                    timeout=ESPERA_SEGUNDOS,
                    cwd=carpeta,
                    env=entorno,
                    check=False,
                )
        except FileNotFoundError as error:
            logger.error("No se encontró el comando %s de Claude Code", self._comando)
            raise ErrorRevision("Sin Claude Code") from error
        except subprocess.TimeoutExpired as error:
            logger.warning("Claude Code no respondió en %s s", ESPERA_SEGUNDOS)
            raise ErrorRevision("Claude Code no respondió a tiempo") from error
        resultado = resultado_de(proceso.stdout)
        if resultado.get("is_error") or resultado.get("subtype") != "success":
            # El texto del resultado explica el error (sesión vencida, límite de uso); nunca
            # trae el documento.
            detalle = str(resultado.get("result") or resultado.get("subtype"))[:200]
            logger.warning("Claude Code no completó la revisión: %s", detalle)
            raise ErrorRevision("Claude Code no completó la revisión")
        try:
            respuesta = RespuestaIa.model_validate(resultado.get("structured_output"))
        except ValidationError as error:
            logger.warning("Claude Code devolvió una revisión que no cumple el esquema")
            raise ErrorRevision("Respuesta fuera del esquema") from error
        return revision_de(respuesta, categorias)
