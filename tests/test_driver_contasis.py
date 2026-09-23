"""El driver CONTASIS por la fachada: el archivo, lo que queda fuera y lo que no cabe."""
from __future__ import annotations

import base64
import io
from datetime import datetime

import pytest

from contaperu import api
from contaperu.drivers import contasis, contrato

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "00000123", "fecha_emision": "2026-08-11",
           "fecha_vencimiento": "2026-08-18", "contraparte_tipo_doc": "6", "contraparte_doc": "20607777773",
           "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "100", "igv": "18", "total": "118",
           "concepto": "Compra de materiales"}
CONTAB = {"cuentas": {"gasto": "601101", "ventas": "701101", "cxp": {"PEN": "4212", "USD": "4212"}},
          "usa_centros_costo": False}


def doc(*comprobantes: dict, **libro) -> dict:
    return {"open_accounting": "1.0", "libro": dict(LIBRO, **libro), "comprobantes": list(comprobantes)}


def hoja(resultado: dict):
    openpyxl = pytest.importorskip("openpyxl")
    return openpyxl.load_workbook(io.BytesIO(base64.b64decode(resultado["contenido_base64"]))).active


def test_el_archivo_empieza_en_la_fila_1_con_la_pestana_oficial():
    """Sin las filas 1-13 de la plantilla, con su pestaña, y los espacios del relleno siguen ahí al abrirlo."""
    r = api.exportar(doc(FACTURA, dict(FACTURA, numero="124")), driver="contasis", configuracion=CONTAB)
    assert r["archivo"] == "CONTASIS_COMPRAS_202608_20601234567.xlsx" and r["formato"] == "contasis_xlsx"
    ws = hoja(r)
    assert ws.title == "FORMATO_COMPRAS" and ws.max_row == 2
    assert isinstance(ws["A1"].value, datetime) and ws["A1"].number_format == "mm-dd-yy"
    assert (ws["D1"].value, ws["F1"].value, ws["AF1"].value, ws["AH1"].value) == (
        "F001  ", "123" + " " * 10, "601101    ", "4212      ")
    assert ws["J1"].value == 100 and ws["J1"].number_format == "#,##0.00"
    assert ws["W1"].value == 1 and ws["W1"].number_format == "#,##0.0000"
    assert ws["C1"].number_format == "@" and ws["L1"].value is None and ws["AK1"].value is None
    # Cada columna con su ancho, para que el archivo se lea al abrirlo: las fechas, el nombre y los importes caben.
    anchos = contasis.datos.ANCHOS["compra"]
    assert all(abs(ws.column_dimensions[letra].width - anchos[letra]) < 0.01 for letra, *_ in contasis.datos.COMPRAS)
    assert anchos["B"] >= 12 and anchos["I"] >= 38 and anchos["K"] >= 12 and anchos["AS"] >= 26
    ventas = api.exportar(doc(FACTURA, tipo="venta"), driver="contasis", configuracion=CONTAB)
    assert hoja(ventas).title == "FORMATO_VENTAS" and ventas["archivo"] == "CONTASIS_VENTAS_202608_20601234567.xlsx"


def test_en_soles_el_tipo_de_cambio_no_cambia_el_archivo():
    """En PEN, CONTASIS escribe siempre `1` en su columna de cambio: el T.C. del comprobante no se mira.

    Importa desde el 22-sep-2026, cuando las aplicaciones empezaron a anotarlo también en soles para STARSOFT.
    Aquí el archivo tiene que salir byte a byte igual."""
    sin_tc = api.exportar(doc(FACTURA), driver="contasis", configuracion=CONTAB)
    con_tc = api.exportar(doc(dict(FACTURA, tipo_cambio="3.383")), driver="contasis", configuracion=CONTAB)
    a, b = hoja(sin_tc), hoja(con_tc)
    filas_a = [[c.value for c in f] for f in a.iter_rows()]
    filas_b = [[c.value for c in f] for f in b.iter_rows()]
    assert filas_a == filas_b, "el T.C. en soles no puede mover el registro de CONTASIS"


def test_la_constancia_de_la_detraccion_llena_sus_dos_columnas():
    """Las columnas U y V existían declaradas y se escribían vacías desde el 12-sep-2026 («no pongas nada»).

    El 22-sep-2026 John pidió lo contrario: que la constancia salga en cualquier destino que tenga el campo. Sin
    depositar sale el comodín; con el vóucher pegado, su número y su fecha. Y una compra SIN detracción las deja
    en blanco: son columnas de las que la llevan, no de todas."""
    fila = lambda d: [c.value for c in hoja(api.exportar(doc(dict(FACTURA, **d)), driver="contasis",
                                                         configuracion=CONTAB)).iter_rows().__next__()]
    columna = lambda f, letra: f[ord(letra) - ord("A")]

    # La U es un texto de ancho fijo (20), así que el escritor la rellena con espacios: se compara sin ellos.
    sin = fila({})
    assert columna(sin, "U").strip() == "" and columna(sin, "V") is None

    pendiente = fila({"detraccion": {"codigo": "027", "porcentaje": "4"}})
    assert columna(pendiente, "U").strip() == "999999999", "el comodín mientras no se deposita"
    assert columna(pendiente, "V") is None, "sin fecha no se inventa una"

    pagada = fila({"detraccion": {"codigo": "027", "porcentaje": "4",
                                  "nro_constancia": "00123456789", "fecha_constancia": "2026-08-05"}})
    assert columna(pagada, "U").strip() == "00123456789"
    assert columna(pagada, "V") is not None and columna(pagada, "V").strftime("%d/%m/%Y") == "05/08/2026"


def test_el_recibo_por_honorarios_queda_fuera_del_archivo():
    rh = dict(FACTURA, tipo_cp="02", serie="E001", numero="7", base_gravada="0", igv="0", inafecto="1000",
              total="1000")
    r = api.exportar(doc(FACTURA, rh), driver="contasis", configuracion=CONTAB)
    assert r["comprobantes"] == 1 and r["resumen"]["fuera_del_destino"] == 1 and hoja(r).max_row == 1


@pytest.mark.parametrize("motivo, cambios, libro, imputacion", [
    ("moneda", dict(moneda="EUR", tipo_cambio="4.100"), {}, None),
    ("cambio", dict(moneda="USD"), {}, None),
    ("rango", dict(tipo_cp="03", serie="B001", numero="1", numero_final="80"), {"tipo": "venta"}, None),
    ("ivap", dict(base_gravada="0", igv="0", base_ivap="100", ivap="4", total="104"), {"tipo": "venta"}, None),
    ("largo", dict(id_externo="f1"), {}, {"f1": {"cuenta_contable": "60110100001"}}),
], ids=["moneda", "cambio", "rango", "ivap", "largo"])
def test_lo_que_contasis_no_puede_llevar_se_dice_antes_y_no_sale(motivo, cambios, libro, imputacion):
    d = doc(dict(FACTURA, **cambios), **libro)
    texto = contasis.datos.MOTIVOS[motivo]
    diag = api.diagnosticar(d, configuracion=CONTAB, driver="contasis", imputacion=imputacion)
    assert list(diag["faltantes"]["no_cabe"]) == [texto] and diag["listo_para_exportar"] is False
    with pytest.raises(contrato.NoCabe):
        api.exportar(d, driver="contasis", configuracion=CONTAB, incluir_observados=True, imputacion=imputacion)


def test_un_centro_mas_largo_que_su_columna_no_se_corta():
    d = doc(dict(FACTURA, id_externo="f1"))
    diag = api.diagnosticar(d, configuracion={"cuentas": {"cxp": {"PEN": "4212"}}}, driver="contasis", imputacion={"f1": {"cuenta_contable": "631101", "centro_costo": "OBRA-00001"}})
    assert list(diag["faltantes"]["no_cabe"]) == [contasis.datos.MOTIVOS["largo"]]


def test_un_nombre_o_una_glosa_largos_se_cortan_y_no_detienen_nada():
    """El nombre y la glosa son texto libre: se cortan a 60. Un código, no (ver el test de arriba)."""
    largo = "SERVICIOS INTEGRALES DE MANTENIMIENTO INDUSTRIAL Y MINERO DEL SUR SOCIEDAD ANONIMA CERRADA"
    d = doc(dict(FACTURA, contraparte_nombre=largo, concepto=largo + " " + largo))
    assert api.diagnosticar(d, configuracion=CONTAB, driver="contasis")["listo_para_exportar"] is True
    ws = hoja(api.exportar(d, driver="contasis", configuracion=CONTAB))
    assert ws["I1"].value == largo[:60] and len(ws["AS1"].value) == 60


def test_una_factura_con_reparto_no_sale_a_contasis():
    d = doc(dict(FACTURA, id_externo="f1"))
    imputacion = {"f1": {"reparto": [{"importe": "60", "cuenta_contable": "636301"},
                                     {"importe": "40", "cuenta_contable": "632201"}]}}
    diag = api.diagnosticar(d, configuracion=CONTAB, driver="contasis", imputacion=imputacion)
    # El serie-número como en la línea del asiento (1.1): sin los ceros a la izquierda del número.
    assert diag["faltantes"]["reparto_no_admitido"] == ["F001-123"] and diag["listo_para_exportar"] is False


def test_para_contasis_no_se_piden_sub_diarios_ni_equivalencias():
    """El sub-diario se elige al importar en CONTASIS y el tipo va con su código SUNAT: no hay nada de eso que pedir."""
    diag = api.diagnosticar(doc(FACTURA), configuracion=CONTAB, driver="contasis")
    assert diag["exige"] == ["cuenta_contable", "cuenta_unica"] and diag["sub_diarios"] == {}
    assert diag["listo_para_exportar"] is True and diag["faltantes"]["no_cabe"] == {}


# ── Que sus cuentas sean las que el núcleo decidiría ────────────────────────────────────────────────────────────

def _cuentas_del_asiento(documento: dict, rol: str) -> list[str]:
    """Las cuentas que el asiento del núcleo pone en ese rol, para los mismos comprobantes."""
    asiento = api.generar_asiento(documento, driver="concar", configuracion=CONTAB)["asiento"]
    return [ln["cuenta"] for ln in asiento if ln.get("rol") == rol]


@pytest.mark.parametrize("tipo, base, total, centro", [("compra", "AF", "AH", "AI"), ("venta", "AB", "AD", "Z")])
def test_sus_cuentas_son_las_que_el_nucleo_decidiria(tipo, base, total, centro):
    """`docs/contasis/LEEME.md` promete que «el driver no decide ninguna cuenta»: la de la base sale de
    `asiento.partes_de` y la del total de `asiento.cuenta_tercero`, la misma resolución que usa el asiento de
    CONCAR. Hasta la 2.8 esa promesa estaba escrita y no la afirmaba ningún test.

    **No sustituye al snapshot, que hace otra cosa.** El snapshot caza que una celda CAMBIE, y lo hace bien: al
    mutar la resolución de la cuenta caen 44 de sus casos. Lo que no puede decir es si el valor que congeló era
    el correcto el primer día, porque se generó desde el código de CONTASIS. Esto compara contra una fuente
    independiente —el asiento que el núcleo arma para los mismos comprobantes—, así que caza una divergencia que
    hubiera estado ahí desde siempre, y convierte la frase de la documentación en una aserción.

    Es la misma pareja que ya tiene CONCAR: `test_snapshot_concar` congela sus celdas y
    `test_driver_asiento_neutral` le lleva la contraria. Y la comparación en sí ya existía en
    `test_contrato_drivers` para un driver de registro DE MENTIRA, mientras el de verdad no la tenía.
    """
    documento = doc(FACTURA, dict(FACTURA, serie="F002", numero="00000456", contraparte_doc="20512333797"),
                    tipo=tipo)
    celdas = hoja(api.exportar(documento, driver="contasis", configuracion=CONTAB))
    filas = range(1, len(documento["comprobantes"]) + 1)
    assert [str(celdas[f"{base}{n}"].value or "").strip() for n in filas] == _cuentas_del_asiento(documento,
                                                                                                 "principal")
    assert [str(celdas[f"{total}{n}"].value or "").strip() for n in filas] == _cuentas_del_asiento(documento,
                                                                                                  "tercero")
    # Y el centro, que sale de `lleva_centro`: apagado en esta configuración, va vacío en los dos lados.
    assert all(not str(celdas[f"{centro}{n}"].value or "").strip() for n in filas)
