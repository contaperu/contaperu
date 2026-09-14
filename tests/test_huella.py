"""La huella del asiento (`asiento/huella.py`, 0.8.0): «este contenido ya salió».

El Excel de CONCAR se suma al importarlo: la misma tanda importada dos veces duplica los asientos. La
huella es lo que permite a quien la guarde reconocer la tanda si vuelve a aparecer. Estos tests fijan
qué entra en ella (el contenido del asiento, en su orden) y qué no (el correlativo, el archivo, la
fecha) — y la fórmula misma, con un valor literal: si cambia, cambia a propósito y se anuncia.
"""
from __future__ import annotations

import pytest

from contaperu import asiento as asi
from contaperu import api
from test_diagnosticar import FACTURA, doc
from util import por_la_fachada

# Las facturas escriben su cuenta y su centro: llegan como su imputación (open-accounting 0.3).
generar_asiento = por_la_fachada(api.generar_asiento)
exportar = por_la_fachada(api.exportar)

# La huella de la FACTURA de `test_diagnosticar` con la configuración de fábrica. Si este valor cambia
# es que cambió la fórmula (o el asiento): las huellas guardadas por quien las persista dejan de
# coincidir con las nuevas, y eso se anuncia como cambio de comportamiento.
HUELLA_FACTURA = "04c77b34a131d024e90d33056060d7ccba5ce7cc1e2c1da26bb520a06dbc2f89"


def lineas(**cambios):
    d = generar_asiento(doc(dict(FACTURA, **cambios)), driver="concar")
    return d["asiento"], d["_asiento"]["huella"]


def test_la_misma_entrada_da_la_misma_huella_y_es_la_de_siempre():
    _, a = lineas()
    _, b = lineas()
    assert a == b == HUELLA_FACTURA


# La misma FACTURA en dólares y con detracción (rama `motor-v1`, etapa 1, 14-sep-2026). La 1.0 pasa el tipo de cambio y
# la tasa de la detracción a texto dentro de la línea (hito 0.6), y eso cambia estas dos huellas a propósito, sin tocar
# la de soles. Se fijan antes para que el cambio se vea y se anuncie, en vez de pasar desapercibido.
HUELLA_USD = "7bea763c65e20607bf0caacfff17b7f41e57e9618634807e900fa51b03928300"
HUELLA_DETRACCION = "a51a1da1befd246b0deea4fb81f4b1e43d3033c61aa0fea56654fb2b50b8b582"


def test_la_huella_en_dolares_y_con_detraccion_es_la_de_siempre():
    assert lineas(moneda="USD", tipo_cambio="3.550")[1] == HUELLA_USD
    assert lineas(detraccion={"codigo": "027", "porcentaje": "4"})[1] == HUELLA_DETRACCION


def test_un_centimo_la_cambia():
    assert lineas(total="4956.01", base_gravada="4200.01")[1] != HUELLA_FACTURA


def test_el_correlativo_no_entra():
    """Re-exportar la misma tanda tras un «deshacer» arranca en otro número y sigue siendo la misma tanda."""
    assert generar_asiento(doc(FACTURA), driver="concar", correlativos={"11": 500})["_asiento"]["huella"] == HUELLA_FACTURA


def test_el_orden_de_las_lineas_entra():
    ln, _ = lineas()
    assert asi.huella(ln) == HUELLA_FACTURA
    assert asi.huella(list(reversed(ln))) != HUELLA_FACTURA


def test_es_del_asiento_y_no_del_archivo():
    """El mismo documento exportado a CONCAR y a CSV lleva la MISMA huella: el archivo es otra cosa."""
    d = doc(FACTURA)
    concar = exportar(d, driver="concar")
    csv = exportar(d, driver="csv")
    assert concar["_exportacion"]["huella"] == csv["_exportacion"]["huella"] == HUELLA_FACTURA
    assert concar["resumen"]["huella"] == csv["resumen"]["huella"] == HUELLA_FACTURA   # lo que persiste el portal
    assert concar["_exportacion"] == {"driver": "concar", "archivo": "CONCAR_20601111111_202608_COMPRAS.xlsx",
                                      "huella": HUELLA_FACTURA}


def test_el_sire_no_lleva_huella():
    """Es un registro tributario, no un asiento: no hay líneas de las que sacarla."""
    e = exportar(doc(FACTURA), driver="sire")["_exportacion"]
    assert e == {"driver": "sire", "archivo": e["archivo"]} and "huella" not in e


def test_la_fecha_la_pone_quien_llama():
    """El núcleo no mira el reloj: sin fecha no hay clave; con una válida sale tal cual; una que no es
    AAAA-MM-DD se rechaza en vez de guardarse mal."""
    assert "fecha" not in exportar(doc(FACTURA), driver="concar")["_exportacion"]
    assert exportar(doc(FACTURA), driver="concar", fecha="2026-09-11")["_exportacion"]["fecha"] == "2026-09-11"
    with pytest.raises(api.DocumentoInvalido, match="AAAA-MM-DD"):
        exportar(doc(FACTURA), driver="concar", fecha="11/09/2026")


def test_acepta_lineas_o_sus_diccionarios():
    ln, _ = lineas()
    assert asi.huella(ln) == asi.huella([dict(x) for x in ln])
