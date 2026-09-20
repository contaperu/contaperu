"""El contrato v1 ya cubre lo que un sistema de asientos por JSON necesita: el índice de cada comprobante, un cuerpo que
no es un Excel y lo que no cabe en su formato. Se prueba con `drivers_de_prueba/diario_json.py`, enchufado por entry
points de mentira, como se enchufaría STARSOFT.
"""
from __future__ import annotations

import base64
import copy
import json

import pytest

from contaperu import api, drivers
from contaperu.drivers import contrato
from drivers_de_prueba import diario_json
from util import GOLDEN

CONFIG = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}


class _Entrada:
    name = "diario_json"

    def load(self):
        return diario_json


@pytest.fixture
def registrado(monkeypatch):
    monkeypatch.setattr(drivers, "entry_points", lambda group: [_Entrada()] if group == drivers.GRUPO else [])
    drivers.recargar()
    yield
    monkeypatch.undo()
    drivers.recargar()


def _documento() -> dict:
    return json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))


def test_cumple_el_contrato_v1_como_legacy():
    assert contrato.incumplimientos(diario_json) == []
    assert (contrato.canal(diario_json), contrato.forma(diario_json)) == ("legacy", "desde_lineas")
    assert contrato.acepta_indice(diario_json) and contrato.arma_asientos(diario_json)


def test_cada_asiento_lleva_sus_lineas_y_la_cabecera_de_su_comprobante(registrado):
    documento = _documento()
    r = api.exportar(documento, driver="diario_json", configuracion=CONFIG)
    cuerpo = json.loads(base64.b64decode(r["contenido_base64"]))
    asiento = api.generar_asiento(documento, driver="diario_json", configuracion=CONFIG)
    # Las líneas del archivo son las del asiento, en el mismo orden y sin perder nada.
    assert [linea for a in cuerpo["asientos"] for linea in a["lineas"]] == asiento["asiento"]
    assert r["resumen"]["asientos"] == len(cuerpo["asientos"]) == r["comprobantes"] == 3
    # Cada asiento es de un comprobante: su número es el de sus líneas y su cabecera, la del documento.
    for a, c in zip(cuerpo["asientos"], documento["comprobantes"]):
        assert {linea["correlativo"] for linea in a["lineas"]} == {a["numero"]}
        assert (a["comprobante"]["serie"], a["comprobante"]["contraparte_doc"]) == (c["serie"], c["contraparte_doc"])
    assert r["resumen"]["huella"] == asiento["_asiento"]["huella"]


def test_lo_que_no_cabe_detiene_tambien_a_un_driver_de_asientos(registrado):
    documento = _documento()
    largo = copy.deepcopy(documento)
    largo["comprobantes"][0]["concepto"] = "X" * 61
    with pytest.raises(api.NoCabe, match="glosa de más de 60"):
        api.exportar(largo, driver="diario_json", configuracion=CONFIG)
    diagnostico = api.diagnosticar(largo, driver="diario_json", configuracion=CONFIG)
    assert list(diagnostico["faltantes"]["no_cabe"].values()) == [[diagnostico["saldrian"][0]]]
    assert not diagnostico["listo_para_exportar"]
    assert api.diagnosticar(documento, driver="diario_json", configuracion=CONFIG)["listo_para_exportar"]


def test_los_hechos_tributarios_del_comprobante_llegan_al_driver(registrado):
    """Lo que un driver de ASIENTOS no tenia hasta la 1.4.0, y que uno de REGISTRO siempre tuvo.

    El driver de mentira vuelca `entrada.cabecera.a_dict()` entero, asi que sirve de consumidor real: si un hecho
    del comprobante se cae por el camino, aqui se ve. Es el hueco que destapo STARSOFT —su plantilla mezcla el
    asiento con el registro tributario en la misma fila— y que ningun driver de asientos habia necesitado, porque
    el Excel de CONCAR es contabilidad pura y no tiene ni una columna de destino del IGV.
    """
    documento = _documento()
    documento["comprobantes"][0].update(destino_igv="DGNG", anio_dua="2025", cod_dep_aduanera="118",
                                        contraparte_tipo_doc="6", clasif_bienes="1")
    r = api.exportar(documento, driver="diario_json", configuracion=CONFIG)
    cabecera = json.loads(base64.b64decode(r["contenido_base64"]))["asientos"][0]["comprobante"]

    assert cabecera["destino_igv"] == "DGNG", "el destino del IGV decide una columna entera en STARSOFT"
    assert (cabecera["anio_dua"], cabecera["cod_dep_aduanera"]) == ("2025", "118")
    assert (cabecera["contraparte_tipo_doc"], cabecera["clasif_bienes"]) == ("6", "1")
    # Y los demas hechos tributarios viajan aunque este comprobante no los traiga: la cabecera los declara todos.
    for campo in ("exonerado", "inafecto", "exportacion", "isc", "ivap", "icbper", "otros", "retencion",
                  "valor_no_gravado", "dscto_base", "dscto_igv", "numero_final", "id_contrato"):
        assert campo in cabecera, f"{campo} no llega al driver"


def test_ningun_dato_del_proceso_llega_al_driver(registrado):
    """La otra mitad: `confianza` y `origen` son de la aplicacion que produjo el dato, no hechos contables.

    Un driver que mirara `confianza` estaria decidiendo contabilidad con la certeza de un modelo de lenguaje.
    """
    documento = _documento()
    documento["comprobantes"][0].update(origen="vision", confianza=0.62, archivo_nombre="factura.pdf")
    r = api.exportar(documento, driver="diario_json", configuracion=CONFIG)
    cabecera = json.loads(base64.b64decode(r["contenido_base64"]))["asientos"][0]["comprobante"]

    for campo in ("origen", "confianza", "archivo_nombre", "datos_originales", "estado", "observaciones"):
        assert campo not in cabecera, f"{campo} no es un hecho contable y no debe viajar al driver"
