from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.deudas.dominio.modelos import LugarPago
from app.documentos.dominio.modelos import Capa, Lectura, Riesgo, Senal
from app.pagos.dominio.confianza import CONFIANZA_MAXIMA, comprobaciones, confianza
from app.pagos.dominio.modelos import (
    AnalisisComprobante,
    EstadoComprobante,
    Moneda,
    ResultadoComprobacion,
)
from app.pagos.dominio.reglas import (
    CuotaEsperada,
    comparar_mora,
    cuenta_para_bloqueo,
    estado_tras_analisis,
    evaluar,
    evaluar_prueba_mora,
)
from tests.dobles import TEXTO_PRUEBA_MORA, TEXTO_VOUCHER, VOUCHER

HOY = date(2026, 10, 21)
LECTURA = Lectura(TEXTO_VOUCHER, 0.97, 1)
ESPERADA = CuotaEsperada(
    importe=Decimal("182.40"),
    codigo_pago="54871236",
    empresa="Hidrandina S.A.",
    titular="Valentina Ramos Díaz",
    lugares=(LugarPago.AGENTE,),
    registrada_el=date(2026, 10, 18),
    vencida=False,
)


def revisar(
    lectura: Lectura = LECTURA, esperada: CuotaEsperada = ESPERADA, **cambios: object
) -> tuple[EstadoComprobante, set[str], bool]:
    senales = evaluar(replace(VOUCHER, **cambios), lectura, esperada, HOY)  # type: ignore[arg-type]
    estado = estado_tras_analisis(AnalisisComprobante(VOUCHER, tuple(senales)))
    return estado, {s.codigo for s in senales}, cuenta_para_bloqueo(senales)


def test_un_voucher_de_la_cuota_pasa_sin_reparos() -> None:
    assert revisar() == (EstadoComprobante.LISTO, set(), False)


def test_por_menos_que_la_cuota_solo_vale_en_un_agente_que_cobra_por_partes() -> None:
    parte = Lectura(TEXTO_VOUCHER.replace("182.40", "100.00"), 0.97, 1)
    assert revisar(parte, importe=Decimal("100.00")) == (
        EstadoComprobante.LISTO,
        {"PAGO_PARCIAL"},
        False,
    )
    estado, codigos, cuenta = revisar(parte, importe=Decimal("100.00"), lugar=LugarPago.BILLETERA)
    assert (estado, cuenta) == (EstadoComprobante.RECHAZADO, True)
    assert "MONTO_MENOR" in codigos


def test_por_mas_que_la_cuota_vencida_es_posible_mora_y_no_castiga() -> None:
    vencida = replace(ESPERADA, vencida=True)
    assert revisar(esperada=vencida, importe=Decimal("190.00")) == (
        EstadoComprobante.RECHAZADO,
        {"POSIBLE_MORA", "IMPORTE_NO_CONFIRMADO"},
        False,
    )
    estado, codigos, cuenta = revisar(importe=Decimal("190.00"))
    assert (estado, cuenta, "MONTO_MAYOR" in codigos) == (EstadoComprobante.RECHAZADO, True, True)


@pytest.mark.parametrize(
    ("pagado_el", "codigo"),
    [(date(2026, 10, 22), "FECHA_FUTURA"), (date(2026, 10, 17), "FECHA_ANTERIOR_A_LA_DEUDA")],
)
def test_la_fecha_no_puede_ser_futura_ni_anterior_al_registro_de_la_deuda(
    pagado_el: date, codigo: str
) -> None:
    estado, codigos, cuenta = revisar(pagado_el=pagado_el)
    assert (estado, codigo in codigos, cuenta) == (EstadoComprobante.RECHAZADO, True, True)


def test_otro_codigo_de_pago_se_rechaza_salvo_que_el_texto_traiga_el_de_la_deuda() -> None:
    otra = Lectura(TEXTO_VOUCHER.replace("54871236", "99990000"), 0.97, 1)
    estado, codigos, _ = revisar(lectura=otra, codigo_pago="99990000")
    assert (estado, "CODIGO_DISTINTO" in codigos) == (EstadoComprobante.RECHAZADO, True)
    # La IA leyó mal un dígito, pero el texto trae el suministro de la deuda: vale.
    assert revisar(codigo_pago="54871286")[0] is EstadoComprobante.LISTO
    # Un voucher que muestra el suministro con su dígito verificador también vale.
    con_digito = Lectura(TEXTO_VOUCHER.replace("54871236", "54871236-0"), 0.97, 1)
    assert revisar(lectura=con_digito, codigo_pago="54871236-0")[0] is EstadoComprobante.LISTO


def test_lo_que_no_es_un_comprobante_en_soles_no_sirve() -> None:
    assert revisar(es_comprobante=False)[:2] == (
        EstadoComprobante.RECHAZADO,
        {"NO_ES_COMPROBANTE"},
    )
    assert revisar(moneda=Moneda.DOLARES)[:2] == (EstadoComprobante.RECHAZADO, {"OTRA_MONEDA"})


def test_una_captura_alterada_se_rechaza_aunque_no_se_lea_el_importe() -> None:
    alteracion = Senal(Capa.IA, "POSIBLE_ALTERACION", "Cifras superpuestas.", Riesgo.ALTO)
    senales = (*evaluar(replace(VOUCHER, importe=None), LECTURA, ESPERADA, HOY), alteracion)

    assert estado_tras_analisis(AnalisisComprobante(VOUCHER, senales)) is (
        EstadoComprobante.RECHAZADO
    )
    assert cuenta_para_bloqueo(senales) is True
    # Sin alteración, lo mismo es solo una foto que no se lee: no castiga.
    sin_importe = evaluar(replace(VOUCHER, importe=None), LECTURA, ESPERADA, HOY)
    assert cuenta_para_bloqueo(sin_importe) is False


def test_sin_importe_o_sin_fecha_se_pide_otra_foto_sin_castigo() -> None:
    assert revisar(importe=None)[0] is EstadoComprobante.ILEGIBLE
    assert revisar(pagado_el=None)[0] is EstadoComprobante.ILEGIBLE


def test_otro_lugar_otra_empresa_o_sin_operacion_pasan_con_menos_confianza() -> None:
    estado, codigos, cuenta = revisar(
        lugar=LugarPago.BILLETERA, empresa="Movistar", numero_operacion=None
    )
    assert (estado, cuenta) == (EstadoComprobante.LISTO, False)
    assert codigos == {"LUGAR_NO_ACEPTADO", "EMPRESA_DISTINTA", "SIN_OPERACION"}


def test_la_confianza_baja_con_cada_aviso_y_nunca_llega_a_cien() -> None:
    def puntaje(**cambios: object) -> int:
        datos = replace(VOUCHER, **cambios)  # type: ignore[arg-type]
        senales = evaluar(datos, LECTURA, ESPERADA, HOY)
        return confianza(comprobaciones([(datos, senales)], ESPERADA))

    limpio = puntaje(titular="RAMOS DIAZ VALENTINA")
    assert limpio == CONFIANZA_MAXIMA
    # Sin titular en el voucher, ese criterio vale la mitad.
    assert puntaje() < limpio
    con_avisos = puntaje(lugar=LugarPago.BILLETERA, numero_operacion=None)
    assert con_avisos < limpio
    # Sin código en la deuda no se pudo comparar: la mitad de ese criterio.
    sin_codigo = comprobaciones([(VOUCHER, [])], replace(ESPERADA, codigo_pago=None))
    codigo = next(c for c in sin_codigo if c.codigo == "codigo_pago")
    assert codigo.resultado is ResultadoComprobacion.SIN_DATO
    assert confianza(sin_codigo) < limpio


PRUEBA_MORA = replace(
    VOUCHER, lugar=None, importe=Decimal("196.80"), total=Decimal("196.80"), mora=Decimal("14.40")
)
LECTURA_MORA = Lectura(TEXTO_PRUEBA_MORA, 0.97, 1)


def test_la_prueba_de_una_mora_muestra_mas_que_la_cuota_del_mismo_codigo() -> None:
    vencida = replace(ESPERADA, vencida=True)
    assert evaluar_prueba_mora(PRUEBA_MORA, LECTURA_MORA, vencida, HOY) == []
    sin_mora = evaluar_prueba_mora(
        replace(PRUEBA_MORA, importe=Decimal("182.40"), total=Decimal("182.40")),
        Lectura(TEXTO_PRUEBA_MORA.replace("196.80", "182.40"), 0.97, 1),
        vencida,
        HOY,
    )
    assert [s.codigo for s in sin_mora] == ["SIN_MORA"]
    assert cuenta_para_bloqueo(sin_mora) is True
    otra = Lectura(TEXTO_PRUEBA_MORA.replace("54871236", "99990000"), 0.97, 1)
    ajena = evaluar_prueba_mora(replace(PRUEBA_MORA, codigo_pago="99990000"), otra, vencida, HOY)
    assert [s.codigo for s in ajena] == ["CODIGO_DISTINTO"]


def test_la_mora_declarada_se_compara_con_la_de_la_prueba() -> None:
    assert comparar_mora(PRUEBA_MORA, Decimal("182.40"), Decimal("14.40")) is None
    distinta = comparar_mora(PRUEBA_MORA, Decimal("182.40"), Decimal("30.00"))
    assert distinta is not None and distinta.codigo == "MORA_NO_COINCIDE"
    # Sin la mora aparte, vale lo que excede a la cuota.
    sin_desglose = replace(PRUEBA_MORA, mora=None)
    assert comparar_mora(sin_desglose, Decimal("182.40"), Decimal("14.40")) is None


def test_con_la_mora_aprobada_vale_la_cuota_con_o_sin_ella() -> None:
    aprobada = replace(ESPERADA, vencida=True, mora=Decimal("14.40"))
    con_mora = Lectura(TEXTO_VOUCHER.replace("182.40", "196.80"), 0.97, 1)
    assert revisar(con_mora, aprobada, importe=Decimal("196.80"))[0] is EstadoComprobante.LISTO
    assert revisar(LECTURA, aprobada)[0] is EstadoComprobante.LISTO
    de_mas = Lectura(TEXTO_VOUCHER.replace("182.40", "210.00"), 0.97, 1)
    estado, codigos, cuenta = revisar(de_mas, aprobada, importe=Decimal("210.00"))
    assert (estado, codigos, cuenta) == (EstadoComprobante.RECHAZADO, {"MONTO_MAYOR"}, True)
