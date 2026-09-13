"""El driver CONTASIS por la fachada: el archivo, lo que queda fuera y lo que no cabe."""
from __future__ import annotations

import base64
import io
from datetime import datetime

import pytest

from contaperu import operaciones as op
from contaperu.drivers import contasis, contrato

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "00000123", "fecha_emision": "2026-08-11",
           "fecha_vencimiento": "2026-08-18", "contraparte_tipo_doc": "6", "contraparte_doc": "20607777773",
           "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "100", "igv": "18", "total": "118",
           "concepto": "Compra de materiales", "cuenta_contable": "601101"}
CONTAB = {"cuentas": {"cxp": {"PEN": "4212", "USD": "4212"}}, "usa_centros_costo": False}


def doc(*comprobantes: dict, **libro) -> dict:
    return {"pe_ledger": "0.2", "libro": dict(LIBRO, **libro), "comprobantes": list(comprobantes)}


def hoja(resultado: dict):
    openpyxl = pytest.importorskip("openpyxl")
    return openpyxl.load_workbook(io.BytesIO(base64.b64decode(resultado["contenido_base64"]))).active


def test_el_archivo_empieza_en_la_fila_1_con_la_pestana_oficial():
    """Sin las filas 1-13 de la plantilla, con su pestaña, y los espacios del relleno siguen ahí al abrirlo."""
    r = op.exportar(doc(FACTURA, dict(FACTURA, numero="124")), "contasis", CONTAB)
    assert r["archivo"] == "CONTASIS_20601234567_202608_COMPRAS.xlsx" and r["formato"] == "contasis_xlsx"
    ws = hoja(r)
    assert ws.title == "FORMATO_COMPRAS" and ws.max_row == 2
    assert isinstance(ws["A1"].value, datetime) and ws["A1"].number_format == "mm-dd-yy"
    assert (ws["D1"].value, ws["F1"].value, ws["AF1"].value, ws["AH1"].value) == (
        "F001  ", "123" + " " * 10, "601101    ", "4212      ")
    assert ws["J1"].value == 100 and ws["J1"].number_format == "#,##0.00"
    assert ws["W1"].value == 1 and ws["W1"].number_format == "#,##0.0000"
    assert ws["C1"].number_format == "@" and ws["L1"].value is None and ws["AK1"].value is None
    ventas = op.exportar(doc(dict(FACTURA, cuenta_contable="701101"), tipo="venta"), "contasis", CONTAB)
    assert hoja(ventas).title == "FORMATO_VENTAS" and ventas["archivo"].endswith("_VENTAS.xlsx")


def test_el_recibo_por_honorarios_queda_fuera_del_archivo():
    rh = dict(FACTURA, tipo_cp="02", serie="E001", numero="7", base_gravada="0", igv="0", inafecto="1000",
              total="1000")
    r = op.exportar(doc(FACTURA, rh), "contasis", CONTAB)
    assert r["filas"] == 1 and r["resumen"]["fuera_del_registro"] == 1 and hoja(r).max_row == 1


@pytest.mark.parametrize("motivo, cambios, libro", [
    ("moneda", dict(moneda="EUR", tipo_cambio="4.100"), {}),
    ("cambio", dict(moneda="USD"), {}),
    ("rango", dict(tipo_cp="03", serie="B001", numero="1", numero_final="80", cuenta_contable="701101"),
     {"tipo": "venta"}),
    ("ivap", dict(base_gravada="0", igv="0", base_ivap="100", ivap="4", total="104", cuenta_contable="701101"),
     {"tipo": "venta"}),
    ("largo", dict(cuenta_contable="60110100001"), {}),
], ids=["moneda", "cambio", "rango", "ivap", "largo"])
def test_lo_que_contasis_no_puede_llevar_se_dice_antes_y_no_sale(motivo, cambios, libro):
    d = doc(dict(FACTURA, **cambios), **libro)
    texto = contasis.datos.MOTIVOS[motivo]
    diag = op.diagnosticar(d, CONTAB, driver="contasis")
    assert list(diag["faltantes"]["no_caben"]) == [texto] and diag["listo_para_exportar"] is False
    with pytest.raises(contrato.NoCabe):
        op.exportar(d, "contasis", CONTAB, incluir_observados=True)


def test_un_centro_mas_largo_que_su_columna_no_se_corta():
    d = doc(dict(FACTURA, cuenta_contable="631101", centro_costo="OBRA-00001"))
    diag = op.diagnosticar(d, {"cuentas": {"cxp": {"PEN": "4212"}}}, driver="contasis")
    assert list(diag["faltantes"]["no_caben"]) == [contasis.datos.MOTIVOS["largo"]]


def test_un_nombre_o_una_glosa_largos_se_cortan_y_no_detienen_nada():
    """El nombre y la glosa son texto libre: se cortan a 60. Un código, no (ver el test de arriba)."""
    largo = "SERVICIOS INTEGRALES DE MANTENIMIENTO INDUSTRIAL Y MINERO DEL SUR SOCIEDAD ANONIMA CERRADA"
    d = doc(dict(FACTURA, contraparte_nombre=largo, concepto=largo + " " + largo))
    assert op.diagnosticar(d, CONTAB, driver="contasis")["listo_para_exportar"] is True
    ws = hoja(op.exportar(d, "contasis", CONTAB))
    assert ws["I1"].value == largo[:60] and len(ws["AS1"].value) == 60


def test_una_factura_con_reparto_no_sale_a_contasis():
    d = doc(dict(FACTURA, id_externo="f1", cuenta_contable=""))
    imputacion = {"f1": {"reparto": [{"importe": "60", "cuenta_contable": "636301"},
                                     {"importe": "40", "cuenta_contable": "632201"}]}}
    diag = op.diagnosticar(d, CONTAB, driver="contasis", imputacion=imputacion)
    assert diag["faltantes"]["reparto_no_admitido"] == ["F001-00000123"] and diag["listo_para_exportar"] is False


def test_para_contasis_no_se_piden_sub_diarios_ni_equivalencias():
    """El sub-diario se elige al importar en CONTASIS y el tipo va con su código SUNAT: no hay nada de eso que pedir."""
    diag = op.diagnosticar(doc(FACTURA), CONTAB, driver="contasis")
    assert diag["exige"] == ["cuenta_contable", "cuenta_unica"] and diag["sub_diarios"] == {}
    assert diag["listo_para_exportar"] is True and diag["faltantes"]["no_caben"] == {}
