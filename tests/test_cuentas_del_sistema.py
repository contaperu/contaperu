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
from util import GOLDEN, imputando

# Cuentas a ocho dígitos, como las de STARSOFT: se declaran SOLO las que se apartan de lo general.
CUENTAS_DEL_SISTEMA = {"cxp": {"PEN": "42120001", "USD": "42120002"}, "igv": "40111000"}
CONFIG = {"usa_centros_costo": False}


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
    """Lo de siempre, y es la mitad que importa: esto no mueve a quien ya estaba.

    El ejemplo era CONTASIS hasta que declaró las suyas (2.7). Lo sigue siendo el CSV, que no declara ninguna
    porque no es de ningún sistema: hereda lo general, el PCGE a seis dígitos."""
    assert contrato.cuentas_por_defecto(drivers.obtener("csv")) == {}
    cuentas = api.config_aplicada(driver="csv")["cuentas"]
    assert (cuentas["cxp"]["PEN"], cuentas["igv"]) == ("421201", "401111")
    # Y ninguna cuenta con la que imputar una compra o una venta: desde la 3.0 eso no es configuración.
    assert not {"gasto", "ingreso", "compras", "ventas"} & set(cuentas)
    assert contrato.plan_base(drivers.obtener("csv")) == ()


def test_concar_declara_su_bloque_entero_y_sus_dos_cuentas_del_plan():
    """Hasta la 3.0 CONCAR declaraba UNA cuenta —la del gasto— porque lo general ya era lo suyo, el PCGE a seis
    dígitos. Desde la 3.0 declara el bloque entero, como los otros dos (John, 23-sep-2026): un driver se lee de un
    vistazo y no obliga a ir a buscar qué hereda.

    Y esa cuenta de gasto dejó de imputar: hoy es `compras`, una de las dos filas con las que nace el plan de la
    empresa, para elegirla comprobante a comprobante."""
    declaradas = contrato.cuentas_por_defecto(drivers.obtener("concar"))
    de_fabrica = api.config_aplicada()["cuentas"]
    assert declaradas == {clave: de_fabrica[clave] for clave in declaradas}, (
        "Las cuentas de CONCAR se separaron de las de fábrica. Si es a propósito, cámbialas aquí también.")
    cuentas = api.config_aplicada(driver="concar")["cuentas"]
    assert (cuentas["cxp"]["PEN"], cuentas["igv"], cuentas["clientes"]["PEN"]) == ("421201", "401111", "121201")
    # Las dos del plan NO se funden en la configuración: son de otro oficio.
    assert not {"compras", "ventas"} & set(cuentas)
    assert contrato.plan_base(drivers.obtener("concar")) == ({"codigo": "631101", "tipo": "gasto"},
                                                             {"codigo": "701101", "tipo": "ingreso"})


def test_contasis_declara_las_suyas_enteras_y_hoy_son_las_de_lo_general():
    """CONTASIS las declara todas (John, 22-sep-2026), al revés que CONCAR, para tener dónde escribir el plan real
    de una instalación el día que alguien lo traiga. Hoy coinciden con lo general —usa el PCGE a seis dígitos—, y
    repetir un dato en dos sitios es exactamente lo que hace que uno se quede atrás cuando el otro mejora.

    Este test es el que lo impide: si alguien cambia una cuenta de `CONFIGURACION_GENERAL` y no la cambia aquí, se
    pone rojo. Cuando lleguen las de CONTASIS de verdad, se separan a propósito y se cambia este test con ellas —y
    ese es justo el momento en el que hay que pensarlo."""
    declaradas = contrato.cuentas_por_defecto(drivers.obtener("contasis"))
    de_fabrica = api.config_aplicada()["cuentas"]
    # Las claves, pinchadas: si desaparece una, el bloque deja de ser «entero» y hay que decidirlo, no perderlo.
    assert sorted(declaradas) == ["clientes", "cxp", "cxp_detraccion", "honorarios", "igv", "retencion_4ta"]
    assert declaradas == {clave: de_fabrica[clave] for clave in declaradas}, (
        "Las cuentas de CONTASIS se separaron de las de fábrica. Si es a propósito, cámbialas aquí también.")
    # Su plan es el PCGE a seis dígitos, igual que el de CONCAR; la de compras va marcada `# prevista` en su driver
    # porque no consta en ningún manual (John, 23-sep-2026).
    assert contrato.plan_base(drivers.obtener("contasis")) == ({"codigo": "631101", "tipo": "gasto"},
                                                               {"codigo": "701101", "tipo": "ingreso"})


def test_los_tres_legacy_declaran_cuentas_con_la_misma_forma():
    """Lo que se buscaba al declararlas: que leer los tres drivers no obligue a aprenderse tres convenciones. Desde
    la 3.0 no hay excepción —CONCAR era la última— y los tres declaran las mismas ocho claves."""
    formas = {n: sorted(contrato.cuentas_por_defecto(drivers.obtener(n))) for n in ("concar", "contasis", "starsoft")}
    assert formas["concar"] == formas["contasis"] == formas["starsoft"]
    # Y los tres siembran plan: una cuenta de compras y una de ventas, que es lo que hace falta para elegir.
    for nombre in ("concar", "contasis", "starsoft"):
        assert [f["tipo"] for f in contrato.plan_base(drivers.obtener(nombre))] == ["gasto", "ingreso"], nombre


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
    assert (cuentas["clientes"]["PEN"], cuentas["cxp_detraccion"]["PEN"], cuentas["retencion_4ta"]) == (
        "121201", "421203", "401721")


def test_el_asiento_lleva_la_cuenta_del_sistema_sin_configurar_nada(con_cuentas_propias):
    """El que cuenta: que la cuenta del sistema llegue al archivo, no solo a un dict.

    Es el fallo que esto arregla. La empresa no configuró ninguna cuenta por pagar, y hasta la 2.5 su asiento salía
    con el 421201 de CONCAR. (La cuenta de la base la trae cada comprobante en su imputación desde la 3.0, así que
    el documento llega imputado; lo que se mira aquí son las OTRAS cuentas del asiento.)
    """
    asiento = api.generar_asiento(imputando(_documento(), "62010001"), driver="diario_json",
                                  configuracion=CONFIG)["asiento"]
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
