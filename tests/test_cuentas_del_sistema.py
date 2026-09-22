"""Con qué cuentas nace una empresa según el sistema contable que lleve (2.5).

Hasta aquí las cuentas eran las mismas para todos: las del PCGE a seis dígitos, que es como numeran CONCAR y
CONTASIS. Un sistema que numera de otra forma escribía una cuenta de seis dígitos en su archivo **mientras la
empresa no abriera la pantalla de configuración**, porque lo que falta se rellena solo y se rellenaba con la de
CONCAR. Ahora cada driver puede declarar las suyas, y se apilan en tres capas: fábrica, sistema, empresa.

Se prueba con `drivers_de_prueba/diario_json.py` —un legacy de terceros enchufado por entry points de mentira— y no
con un driver de serie, porque el mecanismo es del contrato y no de ningún sistema en concreto: el día que STARSOFT
declare las suyas, lo que las hace llegar al archivo es lo que se prueba aquí.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api, drivers
from contaperu.drivers import contrato
from drivers_de_prueba import diario_json
from util import GOLDEN

# Cuentas a ocho dígitos, como las de STARSOFT: se declaran SOLO las que se apartan de lo general.
CUENTAS_DEL_SISTEMA = {"cxp": {"PEN": "42120001", "USD": "42120002"}, "igv": "40111000"}
CONFIG = {"cuentas": {"gasto": "62010001"}, "usa_centros_costo": False}


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


@pytest.fixture
def con_cuentas_propias(registrado, monkeypatch):
    """El driver de prueba declarando las suyas. Va parcheado y no escrito en el módulo a propósito: así el driver
    de prueba sigue sirviendo para lo que ya servía, y cada prueba dice qué declara."""
    monkeypatch.setattr(diario_json, "CUENTAS_POR_DEFECTO", CUENTAS_DEL_SISTEMA, raising=False)


def _documento() -> dict:
    return json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))


def test_un_sistema_que_no_las_declara_sigue_con_las_del_pcge():
    """Lo de siempre, y es la mitad que importa: esto no mueve a quien ya estaba."""
    assert contrato.cuentas_por_defecto(drivers.obtener("concar")) == {}
    cuentas = api.config_aplicada(driver="concar")["cuentas"]
    assert (cuentas["cxp"]["PEN"], cuentas["igv"]) == ("421201", "401111")


def test_las_del_sistema_llegan_cuando_la_empresa_no_configuro_nada(con_cuentas_propias):
    cuentas = api.config_aplicada(driver="diario_json")["cuentas"]
    assert (cuentas["cxp"]["PEN"], cuentas["cxp"]["USD"], cuentas["igv"]) == ("42120001", "42120002", "40111000")


def test_la_empresa_manda_sobre_las_del_sistema(con_cuentas_propias):
    """Las del sistema son de dónde parte, no lo que se impone: en cuanto el contador escribe la suya, es la suya."""
    guardada = {"cuentas": {"cxp": {"PEN": "42120099"}}}
    cuentas = api.config_aplicada(guardada, driver="diario_json")["cuentas"]
    assert cuentas["cxp"]["PEN"] == "42120099"
    # Y lo que la empresa no tocó sigue siendo lo del sistema, no lo general: se funde en profundidad.
    assert cuentas["cxp"]["USD"] == "42120002"


def test_lo_que_el_sistema_no_declara_sigue_siendo_lo_general(con_cuentas_propias):
    """Y por eso se declaran solo las que cambian: lo que no diga lo sigue heredando, hoy y cuando lo general mejore."""
    cuentas = api.config_aplicada(driver="diario_json")["cuentas"]
    assert (cuentas["clientes"]["PEN"], cuentas["ventas"], cuentas["retencion_4ta"]) == ("121201", "701101", "401721")


def test_el_asiento_lleva_la_cuenta_del_sistema_sin_configurar_nada(con_cuentas_propias):
    """El que cuenta: que la cuenta del sistema llegue al archivo, no solo a un dict.

    Es el fallo que esto arregla. La empresa no configuró ninguna cuenta por pagar —solo la de gasto, que es lo que
    siembra cualquier alta—, y hasta la 2.5 su asiento salía con el 421201 de CONCAR.
    """
    asiento = api.generar_asiento(_documento(), driver="diario_json", configuracion=CONFIG)["asiento"]
    terceros = {linea["cuenta"] for linea in asiento if linea["rol"] == "tercero"}
    igv = {linea["cuenta"] for linea in asiento if linea["rol"] == "igv"}
    assert terceros == {"42120001"} and igv == {"40111000"}


def test_la_configuracion_de_partida_de_un_sistema_trae_las_suyas_y_solo_su_seccion(con_cuentas_propias):
    """Es lo que una aplicación siembra cuando da de alta una empresa que ya dijo con qué sistema trabaja."""
    partida = api.configuracion_por_defecto("diario_json")
    assert partida["cuentas"]["cxp"]["PEN"] == "42120001"
    assert "diario_json" in partida and "concar" not in partida
    # Y se puede volver a pasar tal cual, que es la promesa de esta función.
    assert api.errores_de_configuracion(partida) == []


def test_sin_driver_la_configuracion_de_partida_no_cambia(con_cuentas_propias):
    """Sin decir el sistema no hay sistema del que tomarlas: lo general es lo general."""
    partida = api.configuracion_por_defecto()
    assert partida["cuentas"]["cxp"]["PEN"] == "421201"
