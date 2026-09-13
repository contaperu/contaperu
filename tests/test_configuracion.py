"""La maquinaria de la configuración declarada (`contaperu/configuracion.py`): validar, valores por defecto y la
descripción para una pantalla. Se prueba con una declaración de ejemplo; las de verdad tienen su propia prueba."""
from __future__ import annotations

import json

import pytest

from contaperu.configuracion import Campo, Columna, ConfiguracionInvalida, describir, por_defecto, validar

CUENTA = r"^([0-9]{2,12})?$"
POR_MONEDA = (Campo("PEN", "texto", "421201", patron=CUENTA), Campo("USD", "texto", "421202", patron=CUENTA))
CAMPOS = (
    Campo("cuentas", "objeto", titulo="Cuentas", campos=(
        Campo("gasto", "texto", "", patron=CUENTA),
        Campo("cxp", "objeto", campos=POR_MONEDA),
    )),
    Campo("usa_centros_costo", "booleano", True),
    Campo("cuentas_con_centro", "lista", ["63", "65"], valores=Campo("", "texto", patron=r"^[0-9]{1,6}$")),
    Campo("tasas", "mapa", {"037": 12}, claves=r"^[0-9]{3}$", valores=Campo("", "numero", admite_nulo=True)),
    Campo("centros_costo", "lista", valores=Campo("", "objeto", campos=(Campo("codigo", "texto"),
                                                                        Campo("nombre", "texto")))),
)
COLUMNAS = {"centro_costo": (
    Columna("centro_costo", "Código de centro de costos", {"compra": "AI", "venta": "Z"}, fija=True),
    Columna("centro_costo_2", "Código de centro de costos 2", {"compra": "AJ", "venta": "AA"}),
    Columna("presupuesto", "Código de presupuesto", {"compra": "AQ", "venta": "AK"}, marcada=True),
)}


def test_lo_que_cumple_no_da_errores_y_lo_que_falta_tampoco():
    assert validar({}, CAMPOS) == []
    assert validar({"cuentas": {"cxp": {"USD": "421299"}}, "tasas": {"030": None, "037": 12.5},
                    "centros_costo": [{"codigo": "OBRA01", "nombre": "Obra"}]}, CAMPOS) == []


def test_una_clave_desconocida_se_dice_con_su_ruta_y_las_que_hay():
    errores = validar({"cuentas": {"cxp": {"EUR": "421201"}}, "tasa_igv": 18}, CAMPOS)
    assert errores == ["`cuentas.cxp.EUR`: clave desconocida; las que hay: PEN, USD",
                       "`tasa_igv`: clave desconocida; las que hay: cuentas, usa_centros_costo, cuentas_con_centro, "
                       "tasas, centros_costo"]


def test_un_tipo_equivocado_se_dice_con_lo_que_llego():
    """«false» en texto no es falso, y «63» suelto no es una lista: hoy recorrería el texto letra por letra."""
    errores = validar({"usa_centros_costo": "false", "cuentas_con_centro": "63", "tasas": {"037": "12"},
                       "cuentas": {"gasto": 659999}}, CAMPOS)
    assert errores == ['`usa_centros_costo`: se esperaba verdadero o falso y llegó el texto "false"',
                       '`cuentas_con_centro`: se esperaba una lista y llegó el texto "63"',
                       '`tasas.037`: se esperaba un número y llegó el texto "12"',
                       '`cuentas.gasto`: se esperaba un texto y llegó el número 659999']


def test_patrones_de_textos_y_de_claves_y_los_nulos():
    errores = validar({"cuentas": {"gasto": "63-11"}, "cuentas_con_centro": ["63", "6A"],
                       "tasas": {"37": 12}, "usa_centros_costo": None}, CAMPOS)
    assert errores == [f'`cuentas.gasto`: el texto "63-11" no cumple el patrón {CUENTA}',
                       '`cuentas_con_centro[1]`: el texto "6A" no cumple el patrón ^[0-9]{1,6}$',
                       "`tasas.37`: la clave no cumple el patrón ^[0-9]{3}$",
                       "`usa_centros_costo`: se esperaba verdadero o falso y llegó nulo"]
    assert validar({"centros_costo": [{"codigo": "A", "obra": "x"}]}, CAMPOS) == [
        "`centros_costo[0].obra`: clave desconocida; las que hay: codigo, nombre"]


def test_la_seccion_dice_donde_esta_y_no_acepta_algo_que_no_es_un_objeto():
    assert validar({"usa_centros_costo": 1}, CAMPOS, donde="contasis") == [
        "`contasis.usa_centros_costo`: se esperaba verdadero o falso y llegó el número 1"]
    assert validar(["x"], CAMPOS, donde="concar") == ["`concar`: se esperaba un objeto y llegó una lista"]
    assert validar("x", CAMPOS) == ['`configuración`: se esperaba un objeto y llegó el texto "x"']


def test_columnas_elige_entre_las_declaradas_con_la_fija_dentro():
    assert validar({"columnas": {"centro_costo": ["centro_costo", "centro_costo_2"]}}, CAMPOS, COLUMNAS) == []
    errores = validar({"columnas": {"centro_costo": ["centro_costo_2", "centro_costo_3", "centro_costo_2"],
                                    "cuenta_contable": ["x"]}}, CAMPOS, COLUMNAS, donde="contasis")
    assert errores == [
        '`contasis.columnas.centro_costo`: "centro_costo_3" no es una de sus columnas; las que hay: centro_costo, '
        'centro_costo_2, presupuesto',
        "`contasis.columnas.centro_costo`: columna repetida: centro_costo_2",
        '`contasis.columnas.centro_costo`: falta "centro_costo", que es fija: el dato va siempre en ella',
        "`contasis.columnas.cuenta_contable`: ese dato no se elige por columnas; los que sí: centro_costo"]
    assert validar({"columnas": {"centro_costo": "centro_costo"}}, CAMPOS, COLUMNAS) == [
        '`columnas.centro_costo`: se esperaba una lista de columnas y llegó el texto "centro_costo"']


def test_columnas_sin_columnas_declaradas_es_una_clave_desconocida():
    assert validar({"columnas": {"centro_costo": ["centro_costo"]}}, CAMPOS) == [
        "`columnas`: clave desconocida; las que hay: cuentas, usa_centros_costo, cuentas_con_centro, tasas, "
        "centros_costo"]


def test_por_defecto_arma_los_objetos_omite_lo_opcional_y_elige_las_columnas_fijas_y_marcadas():
    assert por_defecto(CAMPOS, COLUMNAS) == {
        "cuentas": {"gasto": "", "cxp": {"PEN": "421201", "USD": "421202"}},
        "usa_centros_costo": True,
        "cuentas_con_centro": ["63", "65"],
        "tasas": {"037": 12},
        "columnas": {"centro_costo": ["centro_costo", "presupuesto"]},
    }
    assert validar(por_defecto(CAMPOS, COLUMNAS), CAMPOS, COLUMNAS) == []


def test_por_defecto_devuelve_una_copia_nueva_cada_vez():
    """Quien cambia lo que recibió no puede cambiar la declaración: la siguiente llamada saldría distinta."""
    primera = por_defecto(CAMPOS)
    primera["cuentas_con_centro"].append("70")
    primera["tasas"]["030"] = 4
    assert por_defecto(CAMPOS)["cuentas_con_centro"] == ["63", "65"]
    assert por_defecto(CAMPOS)["tasas"] == {"037": 12}


def test_describir_da_json_para_pintar_la_pantalla():
    descripcion = describir(CAMPOS, COLUMNAS)
    json.dumps(descripcion)
    cuentas = descripcion["campos"][0]
    assert cuentas["titulo"] == "Cuentas" and cuentas["por_defecto"]["cxp"]["USD"] == "421202"
    assert cuentas["campos"][1]["campos"][0] == {"clave": "PEN", "tipo": "texto", "titulo": "", "ayuda": "",
                                                 "grupo": "", "por_defecto": "421201", "patron": CUENTA}
    tasas = descripcion["campos"][3]
    assert tasas["claves"] == "^[0-9]{3}$" and tasas["valores"]["admite_nulo"] is True
    assert "por_defecto" not in descripcion["campos"][4]
    assert descripcion["columnas"]["centro_costo"][1] == {
        "columna": "centro_costo_2", "titulo": "Código de centro de costos 2", "letra": {"compra": "AJ", "venta": "AA"},
        "fija": False, "marcada": False, "ayuda": ""}


def test_las_declaraciones_repartidas_reproducen_la_configuracion_por_defecto_de_hoy():
    """Declarar no cambia ni un valor: lo general, lo del asiento y la sección de cada sistema, juntos, son la
    `CONFIG_POR_DEFECTO` plana de hoy."""
    from contaperu.asiento.configuracion import CONFIG_POR_DEFECTO, CONFIGURACION_DEL_ASIENTO
    from contaperu.configuracion import CONFIGURACION_GENERAL
    from contaperu.drivers import concar, contasis, contrato

    secciones = {clave: valor for driver in (concar, contasis)
                 for clave, valor in contrato.seccion_por_defecto(driver).items() if clave != "columnas"}
    assert {**por_defecto(CONFIGURACION_GENERAL), **por_defecto(CONFIGURACION_DEL_ASIENTO), **secciones} == \
        CONFIG_POR_DEFECTO


def test_configuracion_invalida_lleva_todos_los_errores():
    errores = validar({"usa_centros_costo": "no", "otra": 1}, CAMPOS)
    with pytest.raises(ConfiguracionInvalida) as e:
        raise ConfiguracionInvalida(errores)
    assert e.value.errores == errores and isinstance(e.value, ValueError)
    assert "`otra`: clave desconocida" in str(e.value)
