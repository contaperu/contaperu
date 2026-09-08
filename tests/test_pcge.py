"""El módulo del PCGE 2026, mientras su tabla siga vacía.

Estos tests fijan la promesa que hace el README: sin la norma codificada, el módulo **no toca
nada** y lo dice. Y ninguna equivalencia entra sin citar el artículo que la respalda.
"""
from __future__ import annotations

import json

import pytest

from contaperu import pcge

LINEAS = [
    {"cuenta": "741101", "debe_haber": "D", "importe": "100.00", "glosa": "DESCUENTO CONCEDIDO"},
    {"cuenta": "701101", "debe_haber": "H", "importe": "1000.00", "glosa": "VENTA"},
]


def test_sin_tabla_no_cambia_nada():
    salida, informe = pcge.adaptar(LINEAS)
    assert salida == LINEAS
    assert informe.sin_tabla and not informe.hubo_cambios
    assert informe.a_dict()["cambios"] == 0


def test_la_tabla_que_viene_de_serie_esta_vacia():
    mapeos, datos = pcge.cargar()
    assert mapeos == []
    assert datos["version"] == "2026" and datos["mapeos"] == []


def test_un_mapeo_sin_cita_no_se_acepta(tmp_path):
    """La regla del proyecto: ninguna regla contable entra sin su fuente."""
    tabla = tmp_path / "pcge.json"
    tabla.write_text(json.dumps({
        "version": "2026",
        "mapeos": [{"de": "74", "a": "70", "modo": "netear", "contra": "701101"}],
    }), encoding="utf-8")
    with pytest.raises(pcge.TablaInvalida, match="no cita la norma"):
        pcge.adaptar(LINEAS, ruta=tabla)


def test_un_neteo_mal_declarado_no_se_acepta(tmp_path):
    tabla = tmp_path / "pcge.json"
    for mapeo in ({"de": "74", "a": "70", "modo": "netear", "cita": "art. 1"},      # sin `contra`
                  {"de": "74", "a": "70", "modo": "inventado", "cita": "art. 1"},
                  {"de": "", "a": "70", "modo": "renombrar", "cita": "art. 1"}):
        tabla.write_text(json.dumps({"version": "2026", "mapeos": [mapeo]}), encoding="utf-8")
        with pytest.raises(pcge.TablaInvalida):
            pcge.adaptar(LINEAS, ruta=tabla)


def test_con_una_tabla_valida_renombra_y_netea(tmp_path):
    """El mecanismo funciona; lo que falta son los datos oficiales, no el código."""
    tabla = tmp_path / "pcge.json"
    tabla.write_text(json.dumps({
        "version": "2026", "fuente": "Norma de ejemplo",
        "mapeos": [
            {"de": "741", "a": "701101", "modo": "netear", "contra": "701101",
             "cita": "articulo de ejemplo, solo para el test"},
        ],
    }), encoding="utf-8")
    salida, informe = pcge.adaptar(LINEAS, ruta=tabla)
    assert not informe.sin_tabla and informe.hubo_cambios
    # La cuenta neteada cambia de cuenta Y de sentido: deja de ser un gasto aparte.
    assert salida[0]["cuenta"] == "701101" and salida[0]["debe_haber"] == "H"
    assert salida[1] == LINEAS[1]
    assert informe.aplicados[0]["cita"].startswith("articulo de ejemplo")
