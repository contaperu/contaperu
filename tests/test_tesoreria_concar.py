"""El libro de tesorería en CONCAR (15.14.0): el pago, calcado del que un CONCAR real aceptó.

El archivo real es de un contribuyente y vive fuera del repositorio (sub-diario de bancos, pago del 03-nov-2026). Lo
que se midió en él, columna a columna, y lo que estas pruebas fijan con datos inventados:

- **una 42 por factura**, nunca agrupada por proveedor, cada una con la cuenta de su compra, el RUC en el anexo (L), el
  tipo y el serie-número de SU factura (R, S), su emisión y su vencimiento (T, U), y la glosa de esa factura en la
  principal (F) y en el detalle (W);
- **la línea del banco al final, sola**, al HABER por la suma exacta, con la 104 de la cuenta en la cuenta Y en el anexo
  (K, L), la sigla `TL` (R), el número del documento del banco (S), la fecha del pago en T y U, y «PAGOS VARIOS»;
- **la fecha del pago** como fecha del comprobante (D) y del tipo de cambio (J) en todas las líneas, con conversión
  `V` (H) y marca `S` (I); y los importes en O y en Q;
- **el sub-diario es el de la cuenta bancaria** (B), y el número del comprobante (C) es el de las compras: mes más un
  correlativo de cuatro dígitos por sub-diario.
"""
from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal

import openpyxl
import pytest

from contaperu import api, asiento

PROVEEDOR = "20602222226"
OTRO = "20607777773"
CUENTAS = [{"id": "bcp-soles", "banco": "BCP", "moneda": "PEN", "cuenta_contable": "104101", "sub_diario": "24"},
           {"id": "bbva-soles", "banco": "BBVA", "moneda": "PEN", "cuenta_contable": "104102", "sub_diario": "26"},
           {"id": "ibk-soles", "banco": "Interbank", "moneda": "PEN", "cuenta_contable": "104103"}]
CONFIG = {"usa_centros_costo": False, "cuentas_bancarias": CUENTAS}


def parte(importe, cuenta, doc, tipo, serie, numero, emision, vence="", glosa=""):
    comprobante = {"tipo_cp": tipo, "serie": serie, "numero": numero, "contraparte_doc": doc,
                   "fecha_emision": emision}
    if vence:
        comprobante["fecha_vencimiento"] = vence
    p = {"importe": importe, "cuenta_contable": cuenta, "contraparte_doc": doc, "comprobante": comprobante}
    if glosa:
        p["glosa"] = glosa
    return p


def pago(id_externo, partes, *, cuenta="bcp-soles", fecha="2026-11-03", constancia="0311261348",
         glosa="PAGOS VARIOS", itf=None):
    total = sum((Decimal(p["importe"]) for p in partes), Decimal(0))
    m = {"cuenta": cuenta, "fecha": fecha, "importe": str(total), "sentido": "cargo", "moneda": "PEN",
         "constancia": constancia, "descripcion": f"{glosa} · {constancia}", "id_externo": id_externo}
    if itf:
        m["itf"] = itf
    return m, {"glosa": glosa, "reparto": partes}


def documento(*pagos):
    return {"open_accounting": api.OPEN_ACCOUNTING,
            "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202611",
                      "tipo": "tesoreria"},
            "movimientos": [m for m, _ in pagos],
            "imputaciones_de_movimientos": {m["id_externo"]: imp for m, imp in pagos}}


def filas(doc, correlativos=None, configuracion=CONFIG):
    archivo = api.exportar_archivo(doc, driver="concar", configuracion=configuracion, correlativos=correlativos)
    hoja = openpyxl.load_workbook(io.BytesIO(archivo.contenido))["CONCAR"]
    cabecera = [c.value for c in hoja[1]]
    columnas = [openpyxl.utils.get_column_letter(i + 1) for i in range(len(cabecera))]
    return archivo, [dict(zip(columnas, fila)) for fila in hoja.iter_rows(min_row=4, values_only=True)]


DOS_FACTURAS = pago("pago-1", [
    parte("1180.00", "421201", PROVEEDOR, "01", "E001", "00003507", "2026-10-24", "2026-11-24",
          glosa="HERRAMIENTAS DE PRUEBA SAC"),
    parte("451.80", "421201", OTRO, "01", "F001", "88", "2026-10-28", glosa="SERVICIOS DE PRUEBA EIRL"),
])


def test_un_pago_de_dos_facturas_sale_como_el_que_concar_acepto():
    archivo, (f1, f2, banco) = filas(documento(DOS_FACTURAS), {"24": 5})
    assert archivo.nombre.startswith("TESORERIA_202611_") and archivo.movimientos == 1
    # Las tres líneas, en el sub-diario de la cuenta y con un solo número de comprobante: el de las compras.
    assert {(f["B"], f["C"]) for f in (f1, f2, banco)} == {("24", "110005")}
    # La fecha del pago en D y en J de todas; la conversión por fecha de venta y la marca de conversión.
    for f in (f1, f2, banco):
        assert f["D"] == f["J"] == dt.datetime(2026, 11, 3)
        assert (f["E"], f["H"], f["I"], f["M"], f["AO"]) == ("MN", "V", "S", None, None)
    # Cada 42 con SU factura: cuenta, RUC en el anexo, debe, importe en O y en Q, tipo, número sin ceros, y sus fechas.
    assert (f1["K"], f1["L"], f1["N"], f1["O"], f1["Q"], f1["P"]) == ("421201", PROVEEDOR, "D", 1180.0, 1180.0, None)
    assert (f1["R"], f1["S"], f1["T"], f1["U"]) == ("FT", "E001-3507", dt.datetime(2026, 10, 24),
                                                    dt.datetime(2026, 11, 24))
    assert (f2["L"], f2["O"], f2["S"], f2["T"], f2["U"]) == (OTRO, 451.8, "F001-88", dt.datetime(2026, 10, 28),
                                                             dt.datetime(2026, 10, 28))
    # La glosa de cada factura, en la principal Y en el detalle: en un pago cada 42 es de otra factura.
    assert (f1["F"], f1["W"]) == ("HERRAMIENTAS DE PRUEBA SAC", "HERRAMIENTAS DE PRUEBA SAC")
    assert f2["F"] == "SERVICIOS DE PRUEBA EIRL"
    # Y el banco al final: su 104 en la cuenta y en el anexo, al haber por la suma, TL, el número y la fecha del pago.
    assert (banco["K"], banco["L"], banco["N"], banco["O"], banco["Q"]) == ("104101", "104101", "H", 1631.8, 1631.8)
    assert (banco["R"], banco["S"], banco["T"], banco["U"]) == ("TL", "0311261348", dt.datetime(2026, 11, 3),
                                                                dt.datetime(2026, 11, 3))
    assert (banco["F"], banco["W"]) == ("PAGOS VARIOS", "PAGOS VARIOS")


def test_cada_banco_numera_en_su_sub_diario_y_el_resumen_dice_cual_es():
    otro = pago("pago-2", [parte("200.00", "421201", OTRO, "01", "F001", "90", "2026-10-30")],
                cuenta="bbva-soles", constancia="0311261400")
    tercero = pago("pago-3", [parte("50.00", "421201", OTRO, "01", "F001", "91", "2026-10-30")],
                   constancia="0411260900", fecha="2026-11-04")
    archivo, f = filas(documento(DOS_FACTURAS, otro, tercero), {"24": 5, "26": 12})
    assert [(x["B"], x["C"]) for x in f] == [("24", "110005")] * 3 + [("26", "110012")] * 2 + [("24", "110006")] * 2
    sub_diarios = archivo.resumen["sub_diarios"]
    assert (sub_diarios["24"]["desde_codigo"], sub_diarios["24"]["hasta_codigo"], sub_diarios["24"]["comprobantes"]) == (
        "110005", "110006", 2)
    assert sub_diarios["24"]["etiqueta"] == "BCP PEN" and sub_diarios["26"]["etiqueta"] == "BBVA PEN"


def test_sin_correlativo_dado_empieza_en_1():
    _, f = filas(documento(DOS_FACTURAS))
    assert {x["C"] for x in f} == {"110001"}


def test_una_cuenta_sin_sub_diario_para_el_libro_y_dice_cual():
    sin = pago("pago-9", [parte("10.00", "421201", OTRO, "01", "F001", "92", "2026-10-30")], cuenta="ibk-soles")
    with pytest.raises(asiento.CuentaBancariaSinSubDiario) as e:
        filas(documento(DOS_FACTURAS, sin, sin))
    assert e.value.clave == "cuenta_bancaria_sin_sub_diario" and e.value.cuales == ["ibk-soles"]
    # Y diagnosticar lo dice ANTES de exportar, a quien se le pide: el contador, en su maestro.
    d = api.diagnosticar(documento(DOS_FACTURAS, sin), driver="concar", configuracion=CONFIG)
    falta = next(q for q in d["que_falta"] if q["motivo"] == "cuenta_bancaria_sin_sub_diario")
    assert falta["pedir_a"] == "contador" and falta["movimientos"] == ["ibk-soles"]


def test_la_sigla_de_la_linea_del_banco_se_configura():
    config = dict(CONFIG, concar={"tesoreria_tipo_doc": "VB"})
    _, f = filas(documento(DOS_FACTURAS), configuracion=config)
    assert [x["R"] for x in f] == ["FT", "FT", "VB"]


def test_el_itf_va_con_su_voucher_y_la_104_anexada_a_si_misma():
    con_itf = pago("pago-4", [parte("100.00", "421201", OTRO, "01", "F001", "93", "2026-10-30")], itf="0.10",
                   constancia="0411261000", fecha="2026-11-04")
    _, f = filas(documento(con_itf))
    itf, banco_itf = f[2], f[3]
    assert (itf["K"], itf["N"], itf["R"], itf["S"]) == ("641201", "D", "TL", "0411261000")
    assert (banco_itf["K"], banco_itf["L"], banco_itf["N"], banco_itf["O"]) == ("104101", "104101", "H", 0.1)


def test_un_deposito_de_detraccion_lleva_su_factura_en_la_421203():
    """El molde del depósito que anota la aplicación: una parte, a la cuenta de la detracción, con su factura."""
    deposito = pago("dep-1", [parte("142.00", "421203", OTRO, "01", "F001", "88", "2026-10-28")],
                    cuenta="bcp-soles", constancia="318467229", glosa="Detracción 037")
    _, (f421203, banco) = filas(documento(deposito))
    assert (f421203["K"], f421203["R"], f421203["S"], f421203["L"]) == ("421203", "FT", "F001-88", OTRO)
    assert (banco["R"], banco["S"]) == ("TL", "318467229")
