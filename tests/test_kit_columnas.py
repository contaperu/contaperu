"""Un formato de columnas simples declarado como tabla (1.1): quien conoce el formato de su sistema lo describe columna
a columna, con su fuente, y no escribe código de proyección. El CSV de serie está escrito así y sale igual que antes."""
from __future__ import annotations

import types

from contaperu import api
from contaperu.asiento import LineaDiario
from contaperu.drivers import contrato
from contaperu.drivers import csv as driver_csv
from contaperu.drivers.kit.columnas import ColumnaDeLinea, escribir_csv, problemas, rutas

PLANTILLA = "La plantilla de importación de asientos del sistema, con su versión"


def lineas() -> list[LineaDiario]:
    return [LineaDiario(cuenta="631101", debe_haber="D", importe="100.00", rol="principal", glosa="SERVICIO; DE PRUEBA",
                        documento={"tipo_cp": "01", "serie_numero": "F001-123"}),
            LineaDiario(cuenta="421201", debe_haber="H", importe="100.00", rol="tercero",
                        documento={"tipo_cp": "01", "serie_numero": "F001-123"})]


def test_una_tabla_de_columnas_escribe_el_csv():
    columnas = (ColumnaDeLinea("CUENTA", "cuenta", PLANTILLA), ColumnaDeLinea("DH", "debe_haber", PLANTILLA),
                ColumnaDeLinea("IMPORTE", "importe", PLANTILLA, clase="importe"),
                ColumnaDeLinea("DOCUMENTO", "documento.serie_numero", PLANTILLA),
                ColumnaDeLinea("REFERENCIA", "referencia.serie_numero", PLANTILLA),
                ColumnaDeLinea("GLOSA", "glosa", PLANTILLA))
    assert problemas(columnas) == []
    texto = escribir_csv(lineas(), columnas, separador=";", bom=False).decode("utf-8")
    assert texto == ("CUENTA;DH;IMPORTE;DOCUMENTO;REFERENCIA;GLOSA\r\n"
                     '631101;D;100.00;F001-123;;"SERVICIO; DE PRUEBA"\r\n'
                     "421201;H;100.00;F001-123;;\r\n")


def test_cada_columna_dice_su_fuente_y_lee_un_campo_que_existe():
    assert {"cuenta", "documento.tipo_cp", "detraccion.codigo"} <= rutas() and "documento" not in rutas()
    malas = (ColumnaDeLinea("CUENTA", "cuenta", ""), ColumnaDeLinea("CUENTA", "cuenta_contable", PLANTILLA),
             ColumnaDeLinea("TASA", "tasa_igv", PLANTILLA, clase="porcentaje"))
    encontrados = problemas(malas)
    assert any("repite cabeceras: CUENTA" in p for p in encontrados)
    assert any("no dice su fuente" in p for p in encontrados)
    assert any("'cuenta_contable', que no es un campo" in p for p in encontrados)
    assert any("clase 'porcentaje'" in p for p in encontrados)
    assert problemas([("cuenta", "CUENTA")]) == ["COLUMNAS_DE_LINEA es una tupla de kit.columnas.ColumnaDeLinea"]


def test_el_contrato_examina_la_tabla_de_un_driver():
    assert contrato.incumplimientos(driver_csv) == []
    sin_fuente = types.ModuleType("sin_fuente")
    sin_fuente.__dict__.update({k: v for k, v in vars(driver_csv).items() if not k.startswith("__")})
    sin_fuente.COLUMNAS_DE_LINEA = (ColumnaDeLinea("CUENTA", "cuenta", ""),)
    assert any("no dice su fuente" in p for p in contrato.incumplimientos(sin_fuente))


def test_el_csv_de_serie_esta_declarado_y_conserva_su_forma_de_la_0_10():
    """Sus columnas de siempre, en su orden, cada una con su fuente; y `COLUMNAS` como pares (ruta, cabecera)."""
    assert [c.cabecera for c in driver_csv.COLUMNAS_DE_LINEA][:3] == ["sub_diario", "correlativo", "fecha"]
    assert all(c.fuente for c in driver_csv.COLUMNAS_DE_LINEA)
    assert driver_csv.COLUMNAS == [(c.ruta, c.cabecera) for c in driver_csv.COLUMNAS_DE_LINEA]
    assert api.verificar_driver("contaperu.drivers.csv")["cumple"]
