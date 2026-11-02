"""Los lectores de lo que SUNAT ve de un periodo: las inconsistencias por comprobante y el reporte de casillas del 621.

Los archivos de aquí son SINTÉTICOS con la forma que se midió el 01-nov-2026 (las notas de `inconsistencias_comprobante`
y `casillas` en `datos/sunat/sire_api.json`): los rótulos son los de SUNAT, letra por letra, y los datos son inventados.
Lo de un contribuyente real no entra en el repositorio.
"""
from __future__ import annotations

import io
import zipfile
from decimal import Decimal

import pytest

from contaperu import sunat
from contaperu.api import SireInvalido
from contaperu.modelo import clave_de

# La cabecera medida en setiembre de 2026 (un mes presentado): 20 rótulos.
CABECERA = ("Número de Operación|Campo de Registro|Fecha de Emisión del CP|Fecha de pago/vcto|Tipo CP|Serie de CP|"
            "Número de CP|Tipo Doc. Emisor|Número Doc. Emisor|Apellidos y Nombres / Razón Social de Emisor|"
            "Tipo de Moneda|BI Gravada DG|IGV/IPM DG|BI Gravada DGNG|IGV/IPM DGNG|Total CP|Código de Inconsistencia|"
            "Descripción de la Inconsistencia|Monto de la inconsistencia|Semáforo")
# La de octubre (sin presentar) es la misma con «Archivo Cargado» delante: 21 rótulos.
CABECERA_SIN_PRESENTAR = "Archivo Cargado|" + CABECERA

TOTAL_DISTINTO = "El importe Total del CP es distinto al contenido en la Propuesta del RCE"
SUMA_MAYOR = "La sumatoria de los campos 15, 17 y 19 del archivo incorporado por el contribuyente es mayor que la sumatoria"
CANTIDAD = "La cantidad de comprobantes informados en su archivo plano (txt) es distinta a la cantidad contenida en la pro"


def _fila(campo, tipo, serie, numero, doc, codigo, descripcion, monto, semaforo, *, operacion="101"):
    """Una fila con la forma medida: 19 campos, SIN el tipo de documento del emisor."""
    return "|".join([operacion, campo, "2026-09-12 00:00:00", "", tipo, serie, numero, doc, "", "PEN",
                     "100.00", "18.00", "0.00", "0.00", "118.00", codigo, descripcion, monto, semaforo])


FILAS = [
    _fila("25", "01", "F001", "00000123", "20602222226", "324", TOTAL_DISTINTO, "-12.50", "2"),
    _fila("15", "01", "F002", "45", "20607777773", "320", SUMA_MAYOR, "1,250.00", "2"),
    _fila("17", "01", "F002", "45", "20607777773", "320", SUMA_MAYOR, "30.00", "2"),
    # La del archivo entero: sin comprobante y en el campo 0.
    "|".join(["0", "0", "2026-09-30 00:00:00", "", "", "", "", "20131312955", "", "", "0.00", "0.00", "0.00",
              "0.00", "0.00", "331", CANTIDAD, "0.00", "1"]),
]


def _archivo(cabecera: str, filas: list[str]) -> bytes:
    return ("\n".join([cabecera, *filas]) + "\n").encode("utf-8")


def test_lee_lo_que_sunat_ve_de_cada_comprobante_por_su_clave():
    """Cada fila da la clave del comprobante —la de `clave_de`, la misma con que una aplicación sabe si ya lo tiene—,
    el código, el texto de SUNAT, el semáforo, el campo y el monto con su signo. Lo que no nombra comprobante va
    aparte."""
    leido = sunat.leer_inconsistencias(_archivo(CABECERA, FILAS))
    primera = leido["por_comprobante"][0]
    assert primera == {"clave": clave_de("01", "F001", "123", "20602222226"), "codigo": "324",
                       "descripcion": TOTAL_DISTINTO, "semaforo": "2", "campo": "25", "monto": Decimal("-12.50")}
    assert primera["clave"] == ("01", "F001", "123", "20602222226"), "el número va sin ceros, como en la app"
    # El mismo código en dos campos del mismo comprobante: una entrada por campo, cada una con su monto.
    assert [(e["campo"], e["monto"]) for e in leido["por_comprobante"][1:]] == [
        ("15", Decimal("1250.00")), ("17", Decimal("30.00"))]
    assert leido["del_archivo"] == [{"codigo": "331", "descripcion": CANTIDAD, "semaforo": "1", "campo": "0",
                                     "monto": Decimal("0.00")}]


def test_la_fila_va_corrida_un_lugar_y_se_lee_bien_igual():
    """La trampa medida: la cabecera trae «Tipo Doc. Emisor» y la fila no. Fiándose de la cabecera, el documento del
    emisor saldría vacío —la fila trae ahí la razón social— y el código sería el total. Con la cabecera sin ese rótulo,
    cada dato cae en su sitio."""
    leido = sunat.leer_inconsistencias(_archivo(CABECERA, FILAS))
    assert {e["clave"][3] for e in leido["por_comprobante"]} == {"20602222226", "20607777773"}
    assert {e["codigo"] for e in leido["por_comprobante"]} == {"324", "320"}


def test_las_dos_cabeceras_medidas_dan_lo_mismo():
    """La de un mes sin presentar empieza por «Archivo Cargado» y la fila trae ese campo vacío delante. Cada dato se
    busca por su rótulo, así que las dos dan exactamente lo mismo."""
    sin_presentar = _archivo(CABECERA_SIN_PRESENTAR, ["|" + f for f in FILAS])
    assert sunat.leer_inconsistencias(sin_presentar) == sunat.leer_inconsistencias(_archivo(CABECERA, FILAS))


def test_si_sunat_arregla_la_fila_se_sigue_leyendo():
    """Si un día la fila trae el tipo de documento del emisor —tantos campos como la cabecera—, se lee con la cabecera
    entera, sin tocar nada."""
    arreglada = []
    for f in FILAS:
        campos = f.split("|")
        arreglada.append("|".join(campos[:7] + ["6" if campos[4] else ""] + campos[7:]))
    assert sunat.leer_inconsistencias(_archivo(CABECERA, arreglada)) == sunat.leer_inconsistencias(
        _archivo(CABECERA, FILAS))


def test_cada_fila_repetida_se_lee_una_vez():
    """Setiembre trajo cada fila dos veces, idénticas y no seguidas: 3 882 filas que eran 1 941."""
    repetido = sunat.leer_inconsistencias(_archivo(CABECERA, FILAS + FILAS))
    assert repetido == sunat.leer_inconsistencias(_archivo(CABECERA, FILAS))
    assert len(repetido["por_comprobante"]) == 3


def test_lee_el_zip_tal_como_lo_baja_el_ticket_y_con_bom():
    """`ticket_archivo` baja un ZIP con un TXT dentro; el lector lo abre él. Y un BOM no ensucia el primer rótulo."""
    contenido = b"\xef\xbb\xbf" + _archivo(CABECERA, FILAS)
    zipeado = io.BytesIO()
    with zipfile.ZipFile(zipeado, "w") as z:
        z.writestr("20131312955_INCONSISTENCIARCE_20261101000000.txt", contenido)
    assert sunat.leer_inconsistencias(zipeado.getvalue()) == sunat.leer_inconsistencias(_archivo(CABECERA, FILAS))


def test_sin_filas_no_hay_inconsistencias():
    assert sunat.leer_inconsistencias(_archivo(CABECERA, [])) == {"por_comprobante": [], "del_archivo": []}


@pytest.mark.parametrize("cabecera, filas, motivo", [
    (CABECERA.replace("|Semáforo", "|Color"), FILAS, "le falta semaforo"),
    (CABECERA, [f + "|extra|otro" for f in FILAS], "21 campos"),
    (CABECERA, FILAS[:2] + [FILAS[2] + "|extra"], "La línea 4"),
    (CABECERA, [FILAS[0].replace("-12.50", "doce")], "no es un importe"),
])
def test_una_forma_que_no_es_la_medida_falla_con_su_motivo(cabecera, filas, motivo):
    """Un lector que no reconoce la forma no devuelve una lista a medias: dice por qué no puede."""
    with pytest.raises(SireInvalido, match=motivo):
        sunat.leer_inconsistencias(_archivo(cabecera, filas))


# ── El reporte de casillas ───────────────────────────────────────────────────────────────────────────────────────

GUIONES = "-" * 120
CASILLAS = "\n".join([
    "Ventas|Casilla|RVIE contribuyente|Inconsistencias en registros|Propuesta SUNAT|DDJJ N° 1234567890|"
    "Diferencia Propuesta vs DDJJ",
    GUIONES,
    # Como se midió: el tributo no trae registro ni inconsistencias; el total trae el registro y no las inconsistencias;
    # el desglose al 18 % no trae casilla.
    "Ventas netas gravadas(Base Imponible).|100|10,000.00|0.00|10,000.00|9,500.00|500.00",
    "Ventas netas gravadas(Tributo).|101|||1,800.00|1,710.00|90.00",
    "Descuentos concedidos y devolución de ventas(Base Imponible).|102|0.00|0.00|0.00|0.00|0.00",
    "Descuentos con tasa del 18%(Base Imponible).||0.00|0.00|0.00|0.00|0.00",
    "Total(Tributo).|131|1,800.00||1,800.00|1,710.00|90.00",
    "",
    "",
    "Compras|Casilla|Preliminar RCE contribuyente|Inconsistencias en registros|Propuesta SUNAT|DDJJ N° 0|"
    "Diferencia Propuesta vs DDJJ",
    GUIONES,
    "Compras netas destinadas a ventas gravadas (Base Imponible).|107|2,000.00|0.00|2,250.00|2,000.00|250.00",
    "Compras netas gravadas (Tributo).|108|||405.00|360.00|45.00",
    "Impuesto Resultante (Saldo a Favor).|140|1,440.00||1,305.00|1,350.00|-45.00",
])


def test_lee_cada_casilla_con_lo_que_dice_cada_fuente():
    """Dos bloques, ventas y compras, una fila por concepto: el registro del contribuyente, las inconsistencias, la
    propuesta de SUNAT, lo declarado y la diferencia. Los importes con su signo y sin la coma de miles."""
    leido = sunat.leer_casillas(CASILLAS.encode("utf-8"))
    assert leido["numero_de_orden"] == "1234567890", "el de la cabecera de ventas; compras dice 0"
    assert leido["ventas"][0] == {"casilla": "100", "concepto": "Ventas netas gravadas(Base Imponible).",
                                  "registro": Decimal("10000.00"), "inconsistencias": Decimal("0.00"),
                                  "propuesta": Decimal("10000.00"), "declarado": Decimal("9500.00"),
                                  "diferencia": Decimal("500.00")}
    assert [f["casilla"] for f in leido["ventas"]] == ["100", "101", "102", "", "131"]
    assert [f["casilla"] for f in leido["compras"]] == ["107", "108", "140"]
    assert leido["compras"][2]["diferencia"] == Decimal("-45.00")


def test_una_celda_vacia_no_es_cero():
    """En el reporte, una celda vacía es una columna que esa casilla no tiene —el tributo no trae registro ni
    inconsistencias en registros—. Leerla como cero diría que SUNAT miró y no encontró nada."""
    ventas = sunat.leer_casillas(CASILLAS)["ventas"]
    tributo, total = ventas[1], ventas[4]
    assert tributo["registro"] is None and tributo["inconsistencias"] is None
    assert tributo["propuesta"] == Decimal("1800.00")
    assert total["registro"] == Decimal("1800.00") and total["inconsistencias"] is None


def test_el_desglose_va_sin_casilla_debajo_de_la_suya():
    desglose = sunat.leer_casillas(CASILLAS)["ventas"][3]
    assert desglose["casilla"] == "" and desglose["concepto"].startswith("Descuentos con tasa del 18%")


@pytest.mark.parametrize("texto, motivo", [
    ("Esto no es un reporte", "no trae el bloque"),
    (CASILLAS.replace("Ventas|Casilla", "Otros|Casilla"), "abre un bloque «Otros»"),
    (CASILLAS.replace("|Propuesta SUNAT|", "|Propuesta|"), "no son los que se midieron"),
    (CASILLAS.replace("|102|0.00|0.00|0.00|0.00|0.00", "|102|0.00|0.00"), "trae 4 campos"),
    (CASILLAS.replace("10,000.00|0.00|10,000.00", "diez mil|0.00|10,000.00"), "no es un importe"),
    ("Ventas netas gravadas(Base Imponible).|100|1.00|0.00|1.00|1.00|0.00", "antes de la cabecera"),
])
def test_un_reporte_que_no_es_el_medido_falla_con_su_motivo(texto, motivo):
    with pytest.raises(SireInvalido, match=motivo):
        sunat.leer_casillas(texto)
