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
#
# **Cambiaron en la 2.2**, y no la fórmula: la glosa entra en la huella y las líneas derivadas dejaron de
# anteponer `IGV - `, `RET 4TA - ` y `DETRACCION - ` (John, 21-sep-2026). Es la segunda vez que se tocan.
HUELLA_FACTURA = "5cc54f016ba041f83d95480b84bce96574eb2aa17f9c866d375bae6bea255a85"


def lineas(**cambios):
    d = generar_asiento(doc(dict(FACTURA, **cambios)), driver="concar")
    return d["asiento"], d["_asiento"]["huella"]


def _sin_detalle(exportacion: dict) -> dict:
    """`_exportacion` sin lo que dice de cada comprobante ni la versión del motor (hitos 0.4 y B2)."""
    return {k: v for k, v in exportacion.items() if k not in ("comprobantes", "motor")}


def test_la_misma_entrada_da_la_misma_huella_y_es_la_de_siempre():
    _, a = lineas()
    _, b = lineas()
    assert a == b == HUELLA_FACTURA


# La misma FACTURA en dólares y con detracción. Se fijaron con la 0.10 (rama `motor-v1`, etapa 1, 14-sep-2026) y cambiaron
# a propósito en la 1.0, sin tocar la de soles, cuando el tipo de cambio y la tasa de la detracción pasaron a texto
# exacto dentro de la línea (hito 0.6, anunciado en el CHANGELOG). Con la 0.10 eran
# 7bea763c65e20607bf0caacfff17b7f41e57e9618634807e900fa51b03928300 y
# a51a1da1befd246b0deea4fb81f4b1e43d3033c61aa0fea56654fb2b50b8b582.
HUELLA_USD = "cb3af1e5e311eadbf33f71aa0087b600e303e2e8f631c8d90ad10f08214689e4"
HUELLA_DETRACCION = "3c8525988cc772ed9c6589033a84cfc185f0db9e84168f2653c7fced63df64bd"


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
    assert _sin_detalle(concar["_exportacion"]) == {"driver": "concar", "archivo": "CONCAR_COMPRAS_202608_20601111111.xlsx",
                                                    "huella": HUELLA_FACTURA}


def test_el_sire_no_lleva_huella():
    """Es un registro tributario, no un asiento: no hay líneas de las que sacarla."""
    e = exportar(doc(FACTURA), driver="sire")["_exportacion"]
    assert _sin_detalle(e) == {"driver": "sire", "archivo": e["archivo"]} and "huella" not in e


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


def test_cada_comprobante_lleva_su_tramo_su_identidad_y_su_huella():
    """Hito 0.4: los tramos son una partición exacta de las líneas, cada uno cuadra y su huella es la de sus líneas; la
    de la tanda no cambia. En un registro, que no arma asiento, solo la identidad. Y la versión del motor (B2)."""
    from decimal import Decimal

    d = doc(FACTURA, dict(FACTURA, numero="872"))
    asiento = generar_asiento(d, driver="concar")
    comprobantes = asiento["_asiento"]["comprobantes"]
    tramos = [c["lineas"] for c in comprobantes]
    assert tramos[0][0] == 0 and tramos[-1][1] == len(asiento["asiento"])
    assert all(a[1] == b[0] for a, b in zip(tramos, tramos[1:]))
    for c in comprobantes:
        lineas_del_tramo = asiento["asiento"][c["lineas"][0]:c["lineas"][1]]
        debe = sum(Decimal(ln["importe"]) for ln in lineas_del_tramo if ln["debe_haber"] == "D")
        haber = sum(Decimal(ln["importe"]) for ln in lineas_del_tramo if ln["debe_haber"] == "H")
        assert debe == haber and c["huella"] == asi.huella(lineas_del_tramo)
    assert [c["identidad"]["numero"] for c in comprobantes] == ["871", "872"]
    assert comprobantes[0]["identidad"] == {"ruc": "20601111111", "libro": "compra", "tipo_cp": "01", "serie": "E001",
                                            "numero": "871", "contraparte_doc": "20602222226"}
    assert asiento["_asiento"]["motor"] == api.__version__
    solo = generar_asiento(doc(FACTURA), driver="concar")["_asiento"]
    assert solo["huella"] == solo["comprobantes"][0]["huella"] == HUELLA_FACTURA
    exportacion = exportar(d, driver="concar")["_exportacion"]
    assert exportacion["comprobantes"] == comprobantes and exportacion["motor"] == api.__version__
    del_sire = exportar(d, driver="sire")["_exportacion"]["comprobantes"]
    assert del_sire == [{"identidad": c["identidad"]} for c in comprobantes]
