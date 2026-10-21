"""El puente de desarrollo con Claude Code, con un comando `claude` de prueba que registra cómo se
lo llamó y responde lo que se le indique. Con PRUEBAS_CLAUDE_CODE=1 se prueba el real."""

import json
import os
import stat
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.deudas.dominio.modelos import LugarPago
from app.documentos.dominio.modelos import Lectura, TipoArchivo, TipoDocumento
from app.documentos.dominio.puertos import CategoriaConocida, ErrorRevision
from app.documentos.infraestructura.revisor_claude_code import RevisorClaudeCode
from app.pagos.infraestructura.revisor_ia import INSTRUCCIONES_COMPROBANTE, RevisorComprobantesIa
from tests.dobles import TEXTO_RECIBO, TEXTO_YAPE, captura_yape, imagen

RESPUESTA = {
    "legible": True,
    "tipo_documento": "recibo_servicio",
    "naturaleza": "por_pagar",
    "emisor": "Hidrandina S.A.",
    "emisor_ruc": "20132023540",
    "titular_nombre": "VALENTINA RAMOS DIAZ",
    "titular_tipo_documento": None,
    "titular_numero_documento": None,
    "codigo_pago": "54871236",
    "numero_documento": "S001-00451236",
    "periodo": "2026-09",
    "importe_total": "182.40",
    "vence_el": "2026-10-28",
    "cuotas": [],
    "concepto_sugerido": "Luz Hidrandina setiembre 2026",
    "categoria_existente": "Luz",
    "categoria_nueva_sugerida": None,
    "lugar_pago_sugerido": "agente",
    "veredicto": "autentico",
    "motivos": ["Coherente con un recibo de Hidrandina"],
}


def comando(carpeta: Path, resultado: dict) -> Path:
    """Un `claude` que guarda sus argumentos, su entrada y su entorno, y responde `resultado`."""
    script = carpeta / "claude"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"registro = {str(carpeta / 'llamada.json')!r}\n"
        "json.dump({'args': sys.argv[1:], 'entrada': sys.stdin.read(), 'cwd': os.getcwd(),\n"
        "           'clave': os.environ.get('ANTHROPIC_API_KEY')}, open(registro, 'w'))\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        f"print(json.dumps({resultado!r}))\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def revisar(script: Path):  # type: ignore[no-untyped-def]
    return RevisorClaudeCode(str(script), "claude-sonnet-5-5", "high").revisar(
        imagen(1), TipoArchivo.PNG, Lectura(TEXTO_RECIBO, 0.97, 1), [CategoriaConocida("Luz", None)]
    )


def test_devuelve_la_revision_de_claude_code_sin_herramientas_ni_clave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-que-no-debe-viajar")
    script = comando(
        tmp_path, {"type": "result", "subtype": "success", "structured_output": RESPUESTA}
    )

    revision = revisar(script)

    assert revision.veredicto == "autentico"
    assert revision.datos.tipo is TipoDocumento.RECIBO_SERVICIO
    assert str(revision.datos.importe) == "182.40"
    assert revision.datos.categoria == "Luz"
    llamada = json.loads((tmp_path / "llamada.json").read_text())
    args = llamada["args"]
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--setting-sources") + 1] == ""
    assert "--no-session-persistence" in args
    # La sesión de Claude Code autoriza: la clave del entorno no viaja.
    assert llamada["clave"] is None
    # El documento va por la entrada estándar, nunca en los argumentos.
    contenido = json.loads(llamada["entrada"])["message"]["content"]
    assert contenido[0]["type"] == "image"
    assert all(len(a) < 20_000 for a in args)
    assert Path(llamada["cwd"]).name.startswith("deconsta-revision-")


@pytest.mark.parametrize(
    "resultado",
    [
        {"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in"},
        {"type": "result", "subtype": "error_max_turns"},
        {"type": "result", "subtype": "success", "structured_output": {"legible": True}},
    ],
)
def test_un_fallo_de_claude_code_deja_la_revision_incompleta(
    tmp_path: Path, resultado: dict
) -> None:
    with pytest.raises(ErrorRevision):
        revisar(comando(tmp_path, resultado))


def test_sin_el_comando_claude_la_revision_queda_incompleta(tmp_path: Path) -> None:
    with pytest.raises(ErrorRevision):
        revisar(tmp_path / "no-existe")


def test_en_produccion_solo_se_usa_la_api() -> None:
    with pytest.raises(ValidationError, match="solo usa la API"):
        Settings(entorno="produccion", cookie_segura=True, ia_proveedor="claude_code")  # type: ignore[call-arg]


@pytest.mark.skipif(
    os.environ.get("PRUEBAS_CLAUDE_CODE") != "1", reason="Activa con PRUEBAS_CLAUDE_CODE=1"
)
def test_claude_code_real_revisa_un_recibo() -> None:
    revision = RevisorClaudeCode("claude", "claude-sonnet-5-5", "medium").revisar(
        imagen(2), TipoArchivo.PNG, Lectura(TEXTO_RECIBO, 0.97, 1), []
    )
    assert revision.veredicto in {"autentico", "dudoso", "alterado"}


RESPUESTA_COMPROBANTE = {
    "legible": True,
    "es_comprobante": True,
    "lugar": "billetera",
    "medio": "Yape",
    "empresa": "HIDRANDINA - LUZ",
    "codigo_pago": "54871236",
    "titular": None,
    "numero_operacion": "03458821",
    "pagado_el": "2026-10-21",
    "moneda": "PEN",
    "importe_servicio": "182.40",
    "comision": None,
    "importe_total": "182.40",
    "veredicto": "autentico",
    "motivos": ["Coherente con una constancia de Yape"],
}


def test_un_voucher_se_revisa_con_sus_propias_instrucciones_y_esquema(tmp_path: Path) -> None:
    script = comando(
        tmp_path,
        {"type": "result", "subtype": "success", "structured_output": RESPUESTA_COMPROBANTE},
    )
    revisor = RevisorComprobantesIa(RevisorClaudeCode(str(script), "claude-sonnet-5-5", "high"))

    revision = revisor.revisar_comprobante(
        imagen(3), TipoArchivo.PNG, Lectura("Yapeaste! S/182.40", 0.97, 1)
    )

    assert (revision.datos.lugar, revision.datos.importe) == (
        LugarPago.BILLETERA,
        Decimal("182.40"),
    )
    assert revision.datos.pagado_el == date(2026, 10, 21)
    args = json.loads((tmp_path / "llamada.json").read_text())["args"]
    assert args[args.index("--system-prompt") + 1] == INSTRUCCIONES_COMPROBANTE
    assert "importe_servicio" in args[args.index("--json-schema") + 1]


@pytest.mark.skipif(
    os.environ.get("PRUEBAS_CLAUDE_CODE") != "1", reason="Activa con PRUEBAS_CLAUDE_CODE=1"
)
def test_claude_code_real_lee_un_voucher_de_yape() -> None:
    revision = RevisorComprobantesIa(
        RevisorClaudeCode("claude", "claude-sonnet-5-5", "medium")
    ).revisar_comprobante(captura_yape(), TipoArchivo.PNG, Lectura(TEXTO_YAPE, 0.97, 1))
    assert revision.datos.es_comprobante is True
    assert revision.datos.importe == Decimal("182.40")
    assert revision.datos.numero_operacion == "03458821"
