"""La línea de diario neutral y el driver CSV que la escribe.

Es la pieza que convierte a este proyecto en un traductor y no en un exportador de CONCAR:
el asiento sale del vocabulario de un ERP concreto y entra en el del estándar.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contaperu import asiento as asi
from contaperu.drivers import csv as driver_csv
from contaperu.modelo import Comprobante, Libro

CONTAB = asi.config_de(None)
MES = (date(2026, 8, 1), date(2026, 8, 31))
ESQUEMA = Path(__file__).resolve().parents[1] / "estandar" / "pe-ledger.schema.json"


def factura(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="E001", numero="871", fecha_emision="2026-08-10",
                fecha_vencimiento="2026-08-27", contraparte_doc="20602222226",
                contraparte_nombre="PROVEEDOR DE PRUEBA SAC", base_gravada="4200", igv="756",
                total="4956", concepto="SERVICIO DE TRANSPORTE", cuenta_contable="659999",
                centro_costo="CC-64")
    base.update(k)
    return Comprobante(**base)


def test_el_centro_de_referencia_viaja_como_anexo_auxiliar():
    """Con `cc_referencia_en_x`, el centro de una cuenta que no lo lleva en M sale del asiento
    por el campo `anexo_auxiliar` del estándar, no por `centro_costo`. Es correcto —la X es la
    X— pero conviene fijarlo aquí y no descubrirlo desde el MCP o desde el driver CSV."""
    ref = asi.config_de({"concar": {"cc_referencia_en_x": True}})
    filas = asi.asiento(factura(cuenta_contable="603201"), ref, MES, "080001")
    gasto = asi.desde_fila(filas[0])
    assert gasto.centro_costo == "" and gasto.anexo_auxiliar == "CC-64"


def test_la_linea_neutral_dice_lo_mismo_que_la_columna():
    filas = asi.asiento(factura(), CONTAB, MES, "080084")
    gasto, igv, proveedor = asi.a_lineas(filas, CONTAB)

    assert gasto.cuenta == "659999" and gasto.debe_haber == "D" and gasto.importe == "4200.00"
    assert gasto.centro_costo == "CC-64" and gasto.moneda == "PEN"
    assert gasto.sub_diario == "11" and gasto.correlativo == "080084"
    assert gasto.fecha == "2026-08-10"
    assert gasto.documento == {"tipo": "FT", "serie_numero": "E001-871",
                               "fecha_emision": "2026-08-10", "fecha_vencimiento": "2026-08-27"}
    assert igv.cuenta == "401111" and igv.glosa.startswith("IGV - ")
    assert proveedor.cuenta == "421201" and proveedor.debe_haber == "H"
    assert proveedor.contraparte_doc == "20602222226" and proveedor.anexo_auxiliar == "CC-64"


def test_el_codigo_de_moneda_del_erp_vuelve_a_iso():
    """En el Excel la moneda es 'MN' o 'US'; en el estándar, PEN y USD."""
    pen = asi.a_lineas(asi.asiento(factura(), CONTAB, MES, "080001"), CONTAB)[0]
    usd = asi.a_lineas(asi.asiento(factura(moneda="USD", tipo_cambio="3.5"), CONTAB, MES, "080002"), CONTAB)[0]
    assert pen.moneda == "PEN" and usd.moneda == "USD" and usd.tipo_cambio == 3.5


def test_la_linea_de_detraccion_lleva_su_bloque():
    filas = asi.asiento(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
    lineas = asi.a_lineas(filas, CONTAB)
    assert len(lineas) == 5
    det = lineas[-1]
    assert det.cuenta == "421203" and det.debe_haber == "H" and det.importe == "198.00"
    assert det.documento["tipo"] == "DR" and det.documento["serie_numero"] == "9999999999"
    assert det.detraccion == {"codigo_interno": "02702", "tasa": 4.0, "base": "4956.00"}
    assert det.glosa.startswith("DETRACCION - ")


def test_a_dict_no_arrastra_claves_vacias():
    linea = asi.a_lineas(asi.asiento(factura(), CONTAB, MES, "080001"), CONTAB)[1]  # el IGV
    d = linea.a_dict()
    assert "centro_costo" not in d and "referencia" not in d and "detraccion" not in d
    assert d["cuenta"] == "401111"


def test_las_lineas_validan_contra_el_estandar():
    """Lo que produce el motor tiene que caber en el bloque `asiento` de pe-ledger."""
    validador = Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))
    doc = {
        "pe_ledger": "0.1",
        "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                  "periodo": "202608", "tipo": "compra"},
        "asiento": [ln.a_dict() for ln in asi.a_lineas(
            asi.asiento(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084"),
            CONTAB)],
    }
    assert list(validador.iter_errors(doc)) == []


# --- el driver CSV -----------------------------------------------------------------

def libro_compras() -> Libro:
    return Libro(ruc="20601111111", razon_social="EMPRESA DE PRUEBA SAC",
                 periodo="202608", tipo="compra")


def test_el_csv_escribe_una_fila_por_linea():
    contenido, resumen = driver_csv.construir(libro_compras(), [factura()], CONTAB, {"11": 1})
    texto = contenido.decode("utf-8-sig")
    filas = [f for f in texto.split("\r\n") if f]
    assert len(filas) == 4                      # cabecera + 3 lineas
    assert filas[0].startswith("sub_diario;correlativo;fecha;cuenta;debe_haber;importe")
    assert filas[1].split(";")[3:6] == ["659999", "D", "4200.00"]
    assert resumen["filas"] == 3 and resumen["debe"] == resumen["haber"] == "4956.00"


def test_el_csv_lleva_bom_para_que_excel_no_rompa_las_tildes():
    contenido, _ = driver_csv.construir(libro_compras(), [factura()], CONTAB, {"11": 1})
    assert contenido.startswith(b"\xef\xbb\xbf")
    sin_bom, _ = driver_csv.construir(libro_compras(), [factura()], CONTAB, {"11": 1}, bom=False)
    assert not sin_bom.startswith(b"\xef\xbb\xbf")


def test_el_separador_se_puede_cambiar():
    contenido, _ = driver_csv.construir(libro_compras(), [factura()], CONTAB, {"11": 1}, separador=",")
    assert contenido.decode("utf-8-sig").startswith("sub_diario,correlativo")


def test_el_csv_esta_registrado_como_driver():
    from contaperu import drivers

    assert drivers.obtener("csv") is driver_csv
    assert drivers.formato("csv", "compra") == "csv_asiento"
    with pytest.raises(ValueError):
        drivers.obtener("un-erp-que-no-existe")
