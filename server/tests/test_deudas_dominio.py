from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.acceso.dominio.modelos import Rol
from app.deudas.dominio.errores import DeudaInvalida, TransicionInvalida
from app.deudas.dominio.modelos import (
    Cuota,
    Deuda,
    EstadoDeuda,
    EstadoPago,
    LugarPago,
    MotivoEspera,
)
from app.deudas.dominio.registro import (
    CuotaEnviada,
    DatosDeuda,
    campos_corregidos,
    evaluar_registro,
)
from app.documentos.dominio.modelos import (
    Analisis,
    Capa,
    CuotaLeida,
    DatosLeidos,
    Riesgo,
    Senal,
    TipoDocumento,
)
from app.reglas.dominio.evaluacion import Identidad
from app.reglas.dominio.titulares import Documento, TipoDocumentoTitular

HOY = date(2026, 10, 21)
AHORA = datetime(2026, 10, 21, 15, tzinfo=UTC)
GERENTE = Identidad(
    ("Valentina Ramos Díaz",), Documento(TipoDocumentoTitular.DNI, "45678912"), "Tú"
)
LEIDO = DatosLeidos(
    tipo=TipoDocumento.RECIBO_SERVICIO,
    titular_nombre="RAMOS DIAZ VALENTINA",
    codigo_pago="54871236",
    importe=Decimal("1820.40"),
    vence_el=date(2026, 10, 28),
)


def datos(**cambios: object) -> DatosDeuda:
    base: dict[str, object] = {
        "concepto": "Luz de la casa",
        "lugares_pago": ["agente"],
        "cuotas": [CuotaEnviada(date(2026, 10, 28), "1820.40")],
        "titular_nombre": "Valentina Ramos Díaz",
        "titular_tipo_documento": None,
        "titular_numero_documento": None,
        "codigo_pago": "54871236",
        "hoy": HOY,
    }
    return DatosDeuda.crear(**{**base, **cambios})  # type: ignore[arg-type]


def evaluar(
    datos_deuda: DatosDeuda,
    *,
    registra: Rol = Rol.ASISTENTE,
    leido: DatosLeidos | None = LEIDO,
    senales: tuple[Senal, ...] = (),
    limite: Decimal | None = Decimal("2000"),
) -> tuple[MotivoEspera, ...]:
    resultado = evaluar_registro(
        registra=registra,
        datos=datos_deuda,
        analisis=Analisis(leido, senales),
        limite=limite,
        identidades=[GERENTE],
        corregidos=campos_corregidos(datos_deuda, leido),
    )
    return resultado.motivos


def test_los_campos_obligatorios_vacios_se_marcan_uno_por_uno() -> None:
    with pytest.raises(DeudaInvalida) as error:
        datos(concepto="  ", lugares_pago=[], cuotas=[])
    assert set(error.value.campos) == {"concepto", "lugares_pago", "cuotas"}


def test_una_deuda_se_paga_en_uno_o_varios_lugares_de_la_lista() -> None:
    elegidos = datos(lugares_pago=["billetera", "agente", "billetera"]).lugares_pago
    # Sin repetir y siempre en el mismo orden, elija como los elija.
    assert elegidos == (LugarPago.AGENTE, LugarPago.BILLETERA)
    with pytest.raises(DeudaInvalida) as error:
        datos(lugares_pago=["agente", "criptomonedas"])
    assert error.value.campos == {"lugares_pago": "Elige lugares de pago de la lista."}


def test_el_concepto_admite_los_signos_de_un_nombre_de_deuda() -> None:
    assert datos(concepto="Luz de la casa · setiembre").concepto == "Luz de la casa · setiembre"
    assert datos(concepto="Cuota 3/12 – BCP").concepto == "Cuota 3/12 – BCP"
    with pytest.raises(DeudaInvalida) as error:
        datos(concepto="<script>")
    assert set(error.value.campos) == {"concepto"}


def test_cada_cuota_se_valida_en_soles_y_en_orden() -> None:
    with pytest.raises(DeudaInvalida) as error:
        datos(
            cuotas=[
                CuotaEnviada(date(2026, 11, 28), "500.00"),
                CuotaEnviada(date(2026, 10, 28), "500,00"),
                CuotaEnviada(None, "12.345"),
                CuotaEnviada(date(2020, 1, 1), "-3"),
            ]
        )
    assert error.value.campos == {
        "cuotas.1.vence_el": "Cada cuota debe vencer después de la anterior.",
        "cuotas.2.importe": (
            "Escribe un importe en soles con hasta dos decimales, por ejemplo 2900.50."
        ),
        "cuotas.2.vence_el": "Indica la fecha de vencimiento.",
        "cuotas.3.importe": (
            "Escribe un importe en soles con hasta dos decimales, por ejemplo 2900.50."
        ),
        "cuotas.3.vence_el": (
            "Revisa la fecha: no puede ser de hace más de dos años ni de dentro de más de treinta."
        ),
    }


def test_un_cronograma_suma_sus_cuotas_aunque_cambien_de_importe() -> None:
    cronograma = datos(
        cuotas=[CuotaEnviada(date(2026, 11 + i // 2, 15), "350.00") for i in range(2)]
        + [CuotaEnviada(date(2027, 1, 15), "362.75")]
    )
    assert cronograma.importe == Decimal("1062.75")
    assert [c.numero for c in cronograma.cuotas] == [1, 2, 3]


def test_lo_de_la_asistente_sin_excepciones_no_espera_autorizacion() -> None:
    assert evaluar(datos(cuotas=[CuotaEnviada(date(2026, 10, 28), "1820.40")])) == ()


def test_bajar_el_importe_a_mano_no_evita_el_limite() -> None:
    leido = DatosLeidos(**{**LEIDO.__dict__, "importe": Decimal("2400.00")})
    motivos = evaluar(datos(cuotas=[CuotaEnviada(date(2026, 10, 28), "1500.00")]), leido=leido)
    assert motivos == (MotivoEspera.IMPORTE_SOBRE_LIMITE, MotivoEspera.DATOS_CORREGIDOS)


def test_poner_al_gerente_como_titular_no_cambia_lo_que_dice_el_documento() -> None:
    otro = DatosLeidos(**{**LEIDO.__dict__, "titular_nombre": "INMOBILIARIA PRIMAVERA SAC"})
    motivos = evaluar(datos(), leido=otro)
    assert motivos == (MotivoEspera.TITULAR_DISTINTO,)


def test_cambiar_el_codigo_de_pago_espera_autorizacion() -> None:
    assert evaluar(datos(codigo_pago="11112222")) == (MotivoEspera.DATOS_CORREGIDOS,)


def test_un_documento_dudoso_o_sin_revision_espera_autorizacion() -> None:
    dudosa = Senal(Capa.IA, "AUTENTICIDAD_DUDOSA", "Tipografía distinta.", Riesgo.MEDIO)
    assert evaluar(datos(), senales=(dudosa,)) == (MotivoEspera.DOCUMENTO_DUDOSO,)
    # Sin lectura de la IA no hay nada con qué contrastar: también espera.
    sin_revision = Senal(Capa.IA, "REVISION_INCOMPLETA", "No se completó.", Riesgo.MEDIO)
    assert evaluar(datos(), leido=None, senales=(sin_revision,)) == (MotivoEspera.DOCUMENTO_DUDOSO,)


def test_al_gerente_no_se_le_detiene_solo_se_le_advierte() -> None:
    otro = DatosLeidos(**{**LEIDO.__dict__, "titular_nombre": "INMOBILIARIA PRIMAVERA SAC"})
    resultado = evaluar_registro(
        registra=Rol.GERENTE,
        datos=datos(),
        analisis=Analisis(otro),
        limite=Decimal("100"),
        identidades=[GERENTE],
        corregidos=(),
    )
    assert resultado.motivos == ()
    assert resultado.avisos == (
        "El titular del documento no eres tú ni uno de tus titulares autorizados.",
    )


def test_los_campos_corregidos_se_comparan_con_lo_leido() -> None:
    cronograma = DatosLeidos(
        tipo=TipoDocumento.CRONOGRAMA,
        cuotas=(CuotaLeida(1, date(2026, 11, 15), Decimal("350.00")),),
    )
    corregidos = campos_corregidos(
        datos(cuotas=[CuotaEnviada(date(2026, 11, 16), "350.00")], codigo_pago=None), cronograma
    )
    assert corregidos == ("vencimiento",)
    assert campos_corregidos(datos(), None) == ()


def deuda(estado: EstadoDeuda, revision: bool = False, vence_el: date = HOY) -> Deuda:
    return Deuda(
        id=uuid4(),
        gerente_id=uuid4(),
        registrada_por=uuid4(),
        documento_id=uuid4(),
        concepto="Luz",
        categoria_id=None,
        tipo_documento=TipoDocumento.RECIBO_SERVICIO,
        cuotas=(Cuota(1, vence_el, Decimal("10.00")),),
        lugares_pago=(LugarPago.AGENTE,),
        titular_nombre=None,
        titular_documento=None,
        codigo_pago=None,
        estado=estado,
        creado_en=AHORA,
        revision_pendiente=revision,
    )


def test_las_decisiones_del_gerente_siguen_sus_transiciones() -> None:
    por_autorizar = deuda(EstadoDeuda.POR_AUTORIZAR)
    por_autorizar.autorizar(uuid4(), AHORA)
    assert por_autorizar.estado is EstadoDeuda.REGISTRADA
    with pytest.raises(TransicionInvalida):
        por_autorizar.autorizar(uuid4(), AHORA)

    en_revision = deuda(EstadoDeuda.REGISTRADA, revision=True)
    with pytest.raises(TransicionInvalida, match="anúlala"):
        en_revision.rechazar(uuid4(), AHORA, "No es mía")
    en_revision.dar_visto_bueno(uuid4(), AHORA)
    assert not en_revision.revision_pendiente
    en_revision.anular(uuid4(), AHORA, "Se pagó por otro medio")
    assert en_revision.estado is EstadoDeuda.ANULADA
    with pytest.raises(TransicionInvalida, match="ya fue anulada"):
        en_revision.anular(uuid4(), AHORA, "Otra vez")


def test_una_deuda_vencida_cuenta_sus_dias_mientras_se_pueda_pagar() -> None:
    atrasada = date(2026, 10, 10)
    assert deuda(EstadoDeuda.REGISTRADA, vence_el=atrasada).vencida_hace(HOY) == 11
    assert deuda(EstadoDeuda.POR_AUTORIZAR, vence_el=atrasada).vencida_hace(HOY) == 11
    # Hoy todavía no está vencida.
    assert deuda(EstadoDeuda.REGISTRADA).vencida_hace(HOY) is None
    # Una anulada o rechazada ya no se paga: no está vencida.
    assert deuda(EstadoDeuda.ANULADA, vence_el=atrasada).vencida_hace(HOY) is None
    assert deuda(EstadoDeuda.RECHAZADA, vence_el=atrasada).vencida_hace(HOY) is None


def cronograma(*pagos: EstadoPago | None) -> Deuda:
    return Deuda(
        id=uuid4(),
        gerente_id=uuid4(),
        registrada_por=uuid4(),
        documento_id=uuid4(),
        concepto="Préstamo",
        categoria_id=None,
        tipo_documento=TipoDocumento.CRONOGRAMA,
        cuotas=tuple(
            Cuota(i + 1, date(2026, 9 + i, 15), Decimal("350.00"), pago)
            for i, pago in enumerate(pagos)
        ),
        lugares_pago=(LugarPago.AGENTE,),
        titular_nombre=None,
        titular_documento=None,
        codigo_pago=None,
        estado=EstadoDeuda.REGISTRADA,
        creado_en=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_la_deuda_vencida_se_cuenta_desde_su_primera_cuota_sin_pagar() -> None:
    assert cronograma(None, None).vencida_hace(HOY) == 36
    # Pagada la de setiembre, la de octubre vence el 15: lleva 6 días.
    assert cronograma(EstadoPago.CONFIRMADO, None).vencida_hace(HOY) == 6
    assert cronograma(EstadoPago.CONFIRMADO, EstadoPago.POR_VERIFICAR).vencida_hace(HOY) is None


def test_no_se_anula_una_deuda_con_un_pago_por_verificar_ni_una_ya_pagada() -> None:
    with pytest.raises(TransicionInvalida, match="esperando tu verificación"):
        cronograma(EstadoPago.POR_VERIFICAR, None).anular(uuid4(), datetime.now(UTC), "No")
    with pytest.raises(TransicionInvalida, match="ya está pagada"):
        cronograma(EstadoPago.CONFIRMADO).anular(uuid4(), datetime.now(UTC), "No")
    pendiente = cronograma(EstadoPago.CONFIRMADO, None)
    pendiente.anular(uuid4(), datetime.now(UTC), "Se canceló el préstamo")
    assert pendiente.estado is EstadoDeuda.ANULADA
