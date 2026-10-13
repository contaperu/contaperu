"""El pendiente derivado, y el estado de cuenta por contraparte (12.4).

**El primitivo es un número y no hay ningún estado.** `pendiente` es el total menos lo que las aplicaciones
confirmadas dicen que se le aplicó, y la palabra —«por cobrar», «pagado»— es una lectura suya que no se guarda en
ninguna parte. Es el tercer uso del patrón, detrás del `rol` (10.0) y de `detracciones.estado_de` (2.0), y la
razón está medida fuera: en Odoo, un marcador al lado del número se desincronizó dos veces.

Lo que estos casos protegen, además de la resta: que una `propuesto` no mueva un saldo, que dos monedas no se
sumen, que lo que viene de otros meses entre por `partidas_previas` **sin que el motor guarde nada**, y que el
corte y los días los ponga quien llama, porque el núcleo no tiene reloj.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from contaperu import api, aplicaciones as ap
from contaperu.errores import DocumentoInvalido
from contaperu.modelo import CERO, Comprobante
from contaperu.pipeline import preparacion as prep

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202603", "tipo": "compra"}
IDENTIDAD = {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}
FACTURA = {**IDENTIDAD, "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "fecha_emision": "2026-03-05",
           "fecha_vencimiento": "2026-04-05", "moneda": "PEN", "base_gravada": "1000.00", "igv": "180.00",
           "total": "1180.00"}


def pago(importe: str, *, cual: str = "mov-1", fecha: str = "2026-03-20", origen: str = "manual",
         moneda: str = "PEN", a: dict | None = None) -> dict:
    return {"de": {"clase": "movimiento", "datos": {"id_externo": cual}},
            "a": a or {"clase": "comprobante", "datos": dict(IDENTIDAD)},
            "importe": importe, "moneda": moneda, "fecha": fecha, "origen": origen}


def doc(*aplicaciones: dict, comprobantes=(FACTURA,)) -> dict:
    return {"open_accounting": "3.3", "libro": dict(LIBRO),
            "comprobantes": [dict(c) for c in comprobantes], "aplicaciones": list(aplicaciones)}


# --- la resta, que es todo lo que hay ----------------------------------------------------------------------------

def test_el_pendiente_es_el_total_menos_lo_aplicado():
    c = Comprobante(**FACTURA)
    ficha = ap.pendiente_de(c, ap.leer([pago("500.00")]))
    assert (ficha["total"], ficha["aplicado"], ficha["pendiente"]) == (
        Decimal("1180.00"), Decimal("500.00"), Decimal("680.00"))
    assert ficha["moneda"] == "PEN" and ficha["vence"] == "2026-04-05"


def test_sin_ninguna_aplicacion_el_pendiente_es_el_total():
    assert ap.pendiente_de(Comprobante(**FACTURA))["pendiente"] == Decimal("1180.00")


def test_tres_pagos_la_dejan_en_cero_y_el_tercero_no_es_especial():
    """La razón de que el saldo se derive: ninguno de los tres sabe que la cierra, y el orden no importa."""
    tres = [pago("400.00", cual="mov-1"), pago("400.00", cual="mov-2"), pago("380.00", cual="mov-3")]
    c = Comprobante(**FACTURA)
    assert ap.pendiente_de(c, ap.leer(tres))["pendiente"] == CERO
    assert ap.pendiente_de(c, ap.leer(list(reversed(tres))))["pendiente"] == CERO


def test_un_pago_de_mas_deja_el_pendiente_en_negativo_y_no_se_recorta():
    """Un sobrepago es un hecho y el motor no lo esconde: recortarlo a cero perdería la información de que algo
    está mal, que es justo lo que un informe tiene que enseñar."""
    assert ap.pendiente_de(Comprobante(**FACTURA), ap.leer([pago("1500.00")]))["pendiente"] == Decimal("-320.00")


def test_una_propuesta_no_mueve_el_pendiente():
    """Donde vive «`conciliar` propone y nunca confirma»."""
    c = Comprobante(**FACTURA)
    assert ap.pendiente_de(c, ap.leer([pago("500.00", origen="propuesto")]))["pendiente"] == Decimal("1180.00")
    assert ap.pendiente_de(c, ap.leer([pago("500.00", origen="declarado")]))["pendiente"] == Decimal("680.00")


def test_lo_aplicado_en_otra_moneda_se_informa_y_NO_se_resta():
    """Ninguna clave suma dos monedas, igual que en `resumen` desde la 3.4.0. Convertir sería una cifra nueva sin
    caso, y restarla a ciegas sería peor: un saldo falso."""
    ficha = ap.pendiente_de(Comprobante(**FACTURA), ap.leer([pago("500.00"), pago("100.00", moneda="USD")]))
    assert ficha["pendiente"] == Decimal("680.00")
    assert ficha["en_otra_moneda"] == {"USD": Decimal("100.00")}


def test_lo_aplicado_a_otro_documento_no_cuenta_para_este():
    otra = {"clase": "comprobante", "datos": dict(IDENTIDAD, numero="999")}
    assert ap.pendiente_de(Comprobante(**FACTURA), ap.leer([pago("500.00", a=otra)]))["aplicado"] == CERO


def test_la_suma_va_por_documento_y_por_moneda():
    totales = ap.aplicado_por_documento(ap.leer([pago("400.00"), pago("100.00", moneda="USD"),
                                                 pago("300.00", cual="mov-2")]))
    clave = ap.Extremo.de({"clase": "comprobante", "datos": dict(IDENTIDAD)}).clave
    assert totales[clave] == {"PEN": Decimal("700.00"), "USD": Decimal("100.00")}


# --- el corte, que lo pone quien llama ---------------------------------------------------------------------------

def test_el_corte_deja_fuera_lo_posterior():
    aplicadas = ap.leer([pago("400.00", fecha="2026-03-20"), pago("400.00", cual="mov-2", fecha="2026-05-20")])
    assert len(ap.hasta(aplicadas, "2026-03-31")) == 1
    assert len(ap.hasta(aplicadas, "2026-12-31")) == 2


def test_sin_corte_entran_todas():
    aplicadas = ap.leer([pago("400.00"), pago("400.00", cual="mov-2", fecha="2026-05-20")])
    assert len(ap.hasta(aplicadas)) == 2 and len(ap.hasta(aplicadas, None)) == 2


def test_el_nucleo_no_calcula_los_dias_ni_los_tramos():
    """Devuelve `vence` y nada más: los días los da la operación con el corte que le pasen, y los tramos de
    antigüedad no se calculan en ninguna parte —30/60/90 es una convención de gestión sin norma detrás—."""
    ficha = ap.pendiente_de(Comprobante(**FACTURA))
    assert set(ficha) == {"total", "aplicado", "pendiente", "moneda", "vence", "en_otra_moneda"}


# --- las partidas previas: lo que no cabe en un mes --------------------------------------------------------------

def test_una_factura_de_otro_mes_entra_con_su_partida_previa():
    """El caso que obligó a esto: una factura de enero pagada en marzo vive en dos documentos."""
    previas = [{**IDENTIDAD, "total": "1180.00", "aplicado": "400.00", "moneda": "PEN", "vence": "2026-02-10"}]
    r = api.estado_de_cuenta(doc(pago("300.00"), comprobantes=()), partidas_previas=previas)
    assert len(r["documentos"]) == 1
    fila = r["documentos"][0]
    assert fila["de_otro_periodo"] is True
    assert (fila["total"], fila["aplicado"], fila["pendiente"]) == ("1180.00", "700.00", "480.00")
    assert [a["codigo"] for a in r["avisos"]] == []


def test_sin_su_partida_previa_el_pago_no_desaparece_pero_se_avisa():
    """Lo peor que podría hacer es callarlo: el pago existe y su documento no está, así que sale con el total en
    blanco y con el aviso que dice por qué."""
    r = api.estado_de_cuenta(doc(pago("300.00"), comprobantes=()))
    fila = r["documentos"][0]
    assert fila["de_otro_periodo"] is True and fila["total"] == "0.00" and fila["aplicado"] == "300.00"
    assert [a["codigo"] for a in r["avisos"]] == ["PARTIDA_PREVIA_NO_DECLARADA"]


def test_una_partida_previa_se_reconoce_con_el_numero_escrito_de_otra_forma():
    previas = [{**IDENTIDAD, "numero": "00000123", "total": "1180.00", "aplicado": "400.00"}]
    leidas = prep.partidas_previas_de(previas)
    assert list(leidas) == [Comprobante(**FACTURA).clave]


def test_dos_partidas_previas_del_mismo_comprobante_se_rechazan():
    """Dos esconderían un saldo: la segunda taparía a la primera sin que nadie lo notase."""
    with pytest.raises(DocumentoInvalido, match="Dos partidas previas"):
        prep.partidas_previas_de([{**IDENTIDAD, "total": "1.00"}, {**IDENTIDAD, "total": "2.00"}])


def test_una_clave_que_no_es_de_una_partida_previa_se_rechaza():
    with pytest.raises(DocumentoInvalido, match="pendiente"):
        prep.partidas_previas_de([{**IDENTIDAD, "total": "1.00", "pendiente": "1.00"}])


def test_las_partidas_previas_tienen_tope_y_su_molde_es_el_de_claves_previas():
    assert prep.MAXIMO_PARTIDAS_PREVIAS < prep.MAXIMO_CLAVES_PREVIAS, (
        "una clave previa es una comparación y una partida abierta es un saldo: nadie lleva cien mil abiertas")
    with pytest.raises(DocumentoInvalido, match="el tope es"):
        prep.partidas_previas_de([{**IDENTIDAD, "total": "1.00"}] * (prep.MAXIMO_PARTIDAS_PREVIAS + 1))


def test_sin_partidas_previas_no_cambia_nada():
    assert prep.partidas_previas_de(None) == {}
    sin = api.estado_de_cuenta(doc(pago("500.00")))
    con = api.estado_de_cuenta(doc(pago("500.00")), partidas_previas=[])
    assert sin == con


# --- la operación -------------------------------------------------------------------------------------------------

def test_el_estado_de_cuenta_da_el_documento_y_la_contraparte():
    r = api.estado_de_cuenta(doc(pago("500.00")), corte="2026-04-30")
    assert r["corte"] == "2026-04-30"
    fila = r["documentos"][0]
    assert (fila["serie"], fila["numero"], fila["pendiente"]) == ("F001", "123", "680.00")
    assert fila["dias"] == 25                      # vence el 05-04 y el corte es el 30-04
    assert r["por_contraparte"] == [{"contraparte_doc": "20602222226", "nombre": "PROVEEDOR DE PRUEBA SAC",
                                     "moneda": "PEN", "documentos": 1, "total": "1180.00",
                                     "aplicado": "500.00", "pendiente": "680.00"}]


def test_sin_corte_no_hay_dias():
    """El núcleo no tiene reloj: sin una fecha de quien llama, no hay nada que restar."""
    r = api.estado_de_cuenta(doc(pago("500.00")))
    assert r["corte"] is None and r["documentos"][0]["dias"] is None


def test_lo_que_vence_despues_del_corte_da_dias_negativos():
    r = api.estado_de_cuenta(doc(pago("500.00")), corte="2026-03-31")
    assert r["documentos"][0]["dias"] == -5


def test_el_corte_deja_fuera_un_pago_posterior_y_lo_dice():
    r = api.estado_de_cuenta(doc(pago("500.00", fecha="2026-05-20")), corte="2026-03-31")
    assert r["documentos"][0]["pendiente"] == "1180.00"
    assert [a["codigo"] for a in r["avisos"]] == ["APLICACIONES_POSTERIORES_AL_CORTE"]


def test_una_propuesta_se_dice_para_que_el_numero_no_parezca_mal_calculado():
    r = api.estado_de_cuenta(doc(pago("500.00", origen="propuesto")))
    assert r["documentos"][0]["pendiente"] == "1180.00"
    aviso = next(a for a in r["avisos"] if a["codigo"] == "APLICACIONES_PROPUESTAS_NO_CONTADAS")
    assert aviso["cual"] == "1"


def test_lo_aplicado_en_otra_moneda_se_avisa():
    r = api.estado_de_cuenta(doc(pago("100.00", moneda="USD")))
    assert r["documentos"][0]["en_otra_moneda"] == {"USD": "100.00"}
    assert "APLICADO_EN_OTRA_MONEDA" in [a["codigo"] for a in r["avisos"]]


def test_el_saldo_por_contraparte_va_por_moneda_y_nunca_suma_dos():
    """Y por eso es un informe y no una fuente: un saldo en cero no significa que todas sus facturas estén
    pagadas, y sumar dos monedas lo esconderría del todo."""
    en_dolares = dict(FACTURA, serie="F002", numero="7", moneda="USD", total="300.00",
                      base_gravada="300.00", igv="0")
    r = api.estado_de_cuenta(doc(comprobantes=(FACTURA, en_dolares)))
    assert [(f["moneda"], f["pendiente"]) for f in r["por_contraparte"]] == [("PEN", "1180.00"), ("USD", "300.00")]


def test_el_saldo_por_contraparte_va_de_mas_a_menos():
    otro = dict(FACTURA, serie="F009", numero="1", contraparte_doc="20607777773",
                contraparte_nombre="OTRO PROVEEDOR SAC", total="5000.00", base_gravada="5000.00", igv="0")
    r = api.estado_de_cuenta(doc(comprobantes=(FACTURA, otro)))
    assert [f["contraparte_doc"] for f in r["por_contraparte"]] == ["20607777773", "20602222226"]


# --- y el guardián que importa ------------------------------------------------------------------------------------

def test_la_respuesta_no_trae_NINGUNA_columna_de_estado():
    """La decisión de la 12.4, hecha cumplir: el número manda y la palabra es una lectura suya. Si alguien añade
    un `estado`, un `pagado` o un `por_pagar` a esta respuesta, este test se pone rojo — y el motivo es que un
    marcador al lado del número se desincroniza, que está medido en Odoo.
    """
    r = api.estado_de_cuenta(doc(pago("500.00")), corte="2026-04-30")
    prohibidas = {"estado", "pagado", "por_pagar", "por_cobrar", "cobrado", "parcial", "cerrado", "conciliado"}
    for fila in r["documentos"] + r["por_contraparte"]:
        assert not prohibidas & set(fila), f"la respuesta trae un estado: {sorted(prohibidas & set(fila))}"


def test_la_respuesta_valida_contra_su_esquema_publicado():
    jsonschema = pytest.importorskip("jsonschema")
    esquema = api.contrato_openconta()["components"]["schemas"]["estado_de_cuenta"]
    r = api.estado_de_cuenta(doc(pago("500.00"), pago("100.00", moneda="USD"), pago("1.00", origen="propuesto")),
                             partidas_previas=[{**IDENTIDAD, "numero": "999", "total": "50.00"}],
                             corte="2026-04-30")
    assert list(jsonschema.Draft202012Validator(esquema).iter_errors(r)) == []


def test_la_operacion_esta_en_la_tabla_y_sale_por_las_tres_puertas():
    operacion = next(o for o in api.OPERACIONES if o.nombre == "estado_de_cuenta")
    assert operacion.ruta == "/v1/estado_de_cuenta" and operacion.metodo == "POST"
    assert operacion.herramienta == "estado_de_cuenta" and operacion.salida == "estado_de_cuenta"
