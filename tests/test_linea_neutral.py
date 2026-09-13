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
from contaperu.drivers import concar as driver_concar
from contaperu import generar as gen
from contaperu.drivers import csv as driver_csv
from contaperu.modelo import Comprobante, Libro
from util import comprobante, con_imputaciones

def configuracion(config_contable: dict | None = None) -> dict:
    """La configuración aplicada (la del entorno sobre la de por defecto) con las imputaciones de las pruebas."""
    return con_imputaciones(asi.config_aplicada(config_contable))


CONTAB = configuracion(None)
MES = (date(2026, 8, 1), date(2026, 8, 31))
ESQUEMA = Path(__file__).resolve().parents[1] / "estandar" / "open-accounting.schema.json"


def factura(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="E001", numero="871", fecha_emision="2026-08-10",
                fecha_vencimiento="2026-08-27", contraparte_doc="20602222226",
                contraparte_nombre="PROVEEDOR DE PRUEBA SAC", base_gravada="4200", igv="756",
                total="4956", concepto="SERVICIO DE TRANSPORTE", cuenta_contable="659999",
                centro_costo="CC-64")
    base.update(k)
    return comprobante(**base)


def test_el_centro_de_referencia_viaja_como_anexo_auxiliar():
    """Con `centro_como_referencia`, el centro de una cuenta que no lo lleva en M sale del asiento
    por el campo `anexo_auxiliar` del estándar, no por `centro_costo`. Es correcto —la X es la
    X— pero conviene fijarlo aquí y no descubrirlo desde el MCP o desde el driver CSV."""
    ref = configuracion({"centro_como_referencia": True})
    filas = driver_concar.filas_de_comprobante(factura(cuenta_contable="603201"), ref, MES, "080001")
    gasto = driver_concar.desde_fila(filas[0])
    assert gasto.centro_costo == "" and gasto.anexo_auxiliar == "CC-64"


def test_la_linea_neutral_dice_lo_mismo_que_la_columna():
    filas = driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080084")
    gasto, igv, proveedor = driver_concar.a_lineas(filas, CONTAB)

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
    pen = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080001"), CONTAB)[0]
    usd = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(moneda="USD", tipo_cambio="3.5"), CONTAB, MES, "080002"), CONTAB)[0]
    assert pen.moneda == "PEN" and usd.moneda == "USD" and usd.tipo_cambio == 3.5


def test_la_linea_de_detraccion_lleva_su_bloque():
    filas = driver_concar.filas_de_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
    lineas = driver_concar.a_lineas(filas, CONTAB)
    assert len(lineas) == 5
    det = lineas[-1]
    assert det.cuenta == "421203" and det.debe_haber == "H" and det.importe == "198.00"
    assert det.documento["tipo"] == "DR" and det.documento["serie_numero"] == "9999999999"
    assert det.detraccion == {"codigo_interno": "02702", "tasa": 4.0, "base": "4956.00"}
    assert det.glosa.startswith("DETRACCION - ")


def test_a_dict_no_arrastra_claves_vacias():
    linea = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080001"), CONTAB)[1]  # el IGV
    d = linea.a_dict()
    assert "centro_costo" not in d and "referencia" not in d and "detraccion" not in d
    assert d["cuenta"] == "401111"


def test_las_lineas_validan_contra_el_estandar():
    """Lo que produce el motor tiene que caber en el bloque `asiento` de open-accounting."""
    validador = Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))
    doc = {
        "open_accounting": "0.3",
        "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                  "periodo": "202608", "tipo": "compra"},
        "asiento": [ln.a_dict() for ln in driver_concar.a_lineas(
            driver_concar.filas_de_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084"),
            CONTAB)],
    }
    assert list(validador.iter_errors(doc)) == []


# --- el motor: la línea neutral como fuente (0.7) -------------------------------------

def test_el_motor_dice_el_rol_y_el_codigo_sunat_de_cada_linea():
    lineas = asi.lineas_del_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
    assert [ln.rol for ln in lineas] == ["principal", "igv", "tercero", "detraccion_tercero", "detraccion"]
    assert all(ln.rol in asi.ROLES for ln in lineas)
    assert lineas[0].documento["tipo_cp"] == "01" and lineas[0].documento["tipo"] == "FT"
    # La detracción no es un comprobante de SUNAT: su documento es el DR, sin código de la Tabla 10;
    # y su referencia es la propia factura, que sí lo tiene.
    assert "tipo_cp" not in lineas[-1].documento and lineas[-1].referencia["tipo_cp"] == "01"
    assert lineas[-1].detraccion["codigo"] == "027" and lineas[-1].detraccion["codigo_interno"] == "02702"


def test_la_glosa_de_la_linea_va_entera_y_el_corte_es_del_driver():
    concepto = "SERVICIO DE TRANSPORTE DE MATERIALES DE CONSTRUCCION A LA OBRA"
    lineas = asi.lineas_del_comprobante(factura(concepto=concepto), CONTAB, MES, "080001")
    assert lineas[0].glosa == concepto and lineas[1].glosa == "IGV - " + concepto
    filas = driver_concar.filas_de_comprobante(factura(concepto=concepto), CONTAB, MES, "080001")
    assert filas[0]["W"] == concepto[:30] and filas[0]["F"] == concepto[:40]


def test_la_tasa_del_igv_viaja_exacta_y_concar_la_redondea():
    reducida = factura(base_gravada="100", igv="10.5", total="110.5")
    assert asi.lineas_del_comprobante(reducida, CONTAB, MES, "080001")[0].tasa_igv == "10.5"
    assert driver_concar.filas_de_comprobante(reducida, CONTAB, MES, "080001")[0]["AO"] == 11


def test_una_nota_de_credito_lleva_los_dos_codigos_de_su_referencia():
    nc = factura(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="E001",
                 ref_numero="871", ref_fecha="2026-08-01")
    principal = asi.lineas_del_comprobante(nc, CONTAB, MES, "080001")[0]
    assert principal.documento["tipo_cp"] == "07" and principal.debe_haber == "H"
    assert principal.referencia == {"tipo": "FT", "tipo_cp": "01", "serie_numero": "E001-871",
                                    "fecha": "2026-08-01"}


def test_lo_que_arma_el_motor_valida_contra_el_estandar():
    validador = Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))
    nc = factura(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="E001", ref_numero="871",
                 ref_fecha="2026-08-01", detraccion={"codigo": "027", "porcentaje": "4"})
    lineas = (asi.lineas_del_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
              + asi.lineas_del_comprobante(nc, CONTAB, MES, "080085")
              + asi.lineas_del_comprobante(factura(tipo_cp="02", retencion="336", igv="0", base_gravada="0",
                                            inafecto="4956"), CONTAB, MES, "080086"))
    doc = {"open_accounting": "0.3",
           "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202608", "tipo": "compra"},
           "asiento": [ln.a_dict() for ln in lineas]}
    assert list(validador.iter_errors(doc)) == []
    assert {ln.rol for ln in lineas} == set(asi.ROLES)


# --- el driver CSV -----------------------------------------------------------------

def libro_compras() -> Libro:
    return Libro(ruc="20601111111", razon_social="EMPRESA DE PRUEBA SAC",
                 periodo="202608", tipo="compra")


def _csv(**opciones_csv) -> bytes:
    """El CSV de una factura como lo arma el núcleo: las líneas numeradas y cuadradas, y el driver que las escribe."""
    libro = libro_compras()
    lineas, _ = asi.lineas_del_libro(libro, [factura()], CONTAB, {"11": 1})
    return driver_csv.desde_lineas(libro, lineas, CONTAB, **opciones_csv)[0]


def test_el_csv_escribe_una_fila_por_linea():
    exp = gen.generar(libro_compras(), [factura()], "csv", config=CONTAB, correlativos={"11": 1})
    resumen = exp.resumen
    texto = exp.contenido.decode("utf-8-sig")
    filas = [f for f in texto.split("\r\n") if f]
    assert len(filas) == 4                      # cabecera + 3 lineas
    assert filas[0].startswith("sub_diario;correlativo;fecha;cuenta;debe_haber;importe")
    assert filas[1].split(";")[3:6] == ["659999", "D", "4200.00"]
    assert resumen["filas"] == 3 and resumen["debe"] == resumen["haber"] == "4956.00"


def test_el_csv_lleva_bom_para_que_excel_no_rompa_las_tildes():
    assert _csv().startswith(b"\xef\xbb\xbf")
    assert not _csv(bom=False).startswith(b"\xef\xbb\xbf")


def test_el_separador_se_puede_cambiar():
    assert _csv(separador=",").decode("utf-8-sig").startswith("sub_diario,correlativo")


def test_el_csv_esta_registrado_como_driver():
    from contaperu import drivers

    assert drivers.obtener("csv") is driver_csv
    assert drivers.formato_de("csv", "compra") == "csv_asiento"
    with pytest.raises(ValueError):
        drivers.obtener("un-erp-que-no-existe")
