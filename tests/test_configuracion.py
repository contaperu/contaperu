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


def test_la_configuracion_de_partida_es_lo_general_y_una_seccion_por_sistema():
    """Lo general en la raíz y la sección de cada sistema que se configura (John, 13-sep-2026). Aplicada para un
    destino sale plana —lo general y lo de ese sistema—, que es como la lee el núcleo."""
    from contaperu import operaciones as op
    from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
    from contaperu.configuracion import CONFIG_POR_DEFECTO

    partida = op.configuracion_por_defecto()
    assert set(partida) - set(CONFIG_POR_DEFECTO) == {"concar", "contasis", "csv"}
    assert {clave: partida[clave] for clave in CONFIG_POR_DEFECTO} == CONFIG_POR_DEFECTO
    assert op.errores_de_configuracion(partida) == []
    del_asiento = {c.clave for c in CONFIGURACION_DEL_ASIENTO}
    assert set(op.config_aplicada(partida, "concar")) == \
        set(CONFIG_POR_DEFECTO) | del_asiento | {"monedas_codigo", "detraccion_area", "columnas"}
    assert set(op.config_aplicada(partida, "csv")) == set(CONFIG_POR_DEFECTO) | del_asiento
    assert set(op.config_aplicada(partida, "contasis")) == set(CONFIG_POR_DEFECTO) | {"medio_pago", "columnas"}
    assert op.config_aplicada(partida, "sire") == op.config_aplicada(partida) == op.config_aplicada()


def test_la_configuracion_se_valida_entera_y_cada_error_dice_adonde_va():
    """Una clave que nadie lee exportaría con el valor de fábrica sin avisar: la forma plana de antes, una clave
    retirada, una inventada o una mal escrita, cada una con su motivo y su ruta."""
    from contaperu import operaciones as op

    errores = op.errores_de_configuracion({
        "tipos": {"01": {"sigla": "FA"}},
        "medio_pago": "003",
        "centro_como_referencia": True,
        "tasa_igv": 18,
        "imputaciones": {},
        "sire": {},
        "usa_centros_costo": "no",
        "concar": {"medio_pago": "001", "columnas": {"centro_costo": ["centro_costo", "centro_costo_2"]}},
        "contasis": {"medio_pago": "3"},
    })
    assert errores == [
        "`tipos` va dentro de la sección de su sistema (concar o csv), no en la raíz",
        "`medio_pago` va dentro de la sección de su sistema (contasis), no en la raíz",
        "`centro_como_referencia` ya no existe: es la columna `anexo_auxiliar` en `concar.columnas.centro_costo`",
        "`tasa_igv`: clave desconocida; en la raíz va lo general (cuentas, usa_centros_costo, centros_costo, "
        "cuentas_con_centro, detraccion_tasas, detraccion_nombres) y una sección por sistema (concar, csv, contasis)",
        "`imputaciones` no va en la configuración: la imputación de cada documento llega aparte (`imputacion`)",
        "`sire` no tiene sección: ese sistema no lleva cuentas y no se configura",
        '`usa_centros_costo`: se esperaba verdadero o falso y llegó el texto "no"',
        "`concar.medio_pago`: clave desconocida; las que hay: tipos, sub_diario_ventas, sub_diario_compras, "
        "sub_diario_detraccion, detraccion_tipo_doc, detraccion_codigos, monedas_codigo, detraccion_area",
        '`concar.columnas.centro_costo`: "centro_costo_2" no es una de sus columnas; las que hay: centro_costo, '
        'anexo_auxiliar, anexo_auxiliar_del_tercero',
        '`contasis.medio_pago`: el texto "3" no cumple el patrón ^[0-9]{3}$',
    ]


def test_una_configuracion_que_no_cumple_no_se_aplica_ni_genera():
    """Por la fachada se detiene al aplicarla; y `generar`, que recibe la ya aplicada, la comprueba para su driver: una
    aplicación que lo llama directamente no se salta nada."""
    from contaperu import generar as gen
    from contaperu import operaciones as op
    from util import cargar_golden

    with pytest.raises(ConfiguracionInvalida) as e:
        op.config_aplicada({"sub_diario_compras": "11"}, "concar")
    assert e.value.errores == ["`sub_diario_compras` va dentro de la sección de su sistema (concar o csv), no en la "
                               "raíz"]
    libro, comprobantes = cargar_golden("compras_202601.json")
    with pytest.raises(ConfiguracionInvalida) as e:
        gen.generar(libro, comprobantes, "concar", config=op.configuracion_por_defecto(), correlativos={"11": 1})
    assert e.value.errores[0].startswith("`concar` es la sección de un sistema: aquí llega la configuración ya "
                                         "aplicada")
    with pytest.raises(ConfiguracionInvalida) as e:
        gen.generar(libro, comprobantes, "concar", config=op.config_aplicada(None, "contasis"), correlativos={"11": 1})
    assert len(e.value.errores) == 1 and e.value.errores[0].startswith("`medio_pago`: clave desconocida")


def test_diagnosticar_dice_la_configuracion_que_no_se_puede_aplicar():
    from contaperu import operaciones as op
    from util import GOLDEN

    doc = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    d = op.diagnosticar(doc, {"medio_pago": "003"}, driver="contasis")
    assert d["listo_para_exportar"] is False and d["por_que_no"] == ["la configuración tiene 1 error"]
    assert d["errores_de_configuracion"] == [
        "`medio_pago` va dentro de la sección de su sistema (contasis), no en la raíz"]
    assert (d["que_falta"][0]["motivo"], d["que_falta"][0]["pedir_a"]) == ("configuracion_invalida", "sistema")
    assert d["totales"]["comprobantes"] == len(doc["comprobantes"]) and d["saldrian"] == []
    en_su_seccion = op.diagnosticar(doc, {"contasis": {"medio_pago": "003"}}, driver="contasis")
    assert en_su_seccion["errores_de_configuracion"] == []


def test_la_cli_dice_la_configuracion_que_no_se_puede_usar(tmp_path, capsys):
    from contaperu import cli
    from util import GOLDEN

    golden = str(GOLDEN / "compras_202601.json")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"tipos": {"01": {"sigla": "FA"}}}), encoding="utf-8")
    assert cli.main(["desde-json", golden, "--driver", "concar", "--salida", str(tmp_path / "s"),
                     "--config", str(config)]) == 2
    err = capsys.readouterr().err
    assert "`tipos` va dentro de la sección de su sistema (concar o csv)" in err and "Traceback" not in err
    assert cli.main(["diagnosticar", golden, "--config", str(config)]) == 1
    assert "!! Configuración: `tipos` va dentro de la sección" in capsys.readouterr().out


def test_configuracion_invalida_lleva_todos_los_errores():
    errores = validar({"usa_centros_costo": "no", "otra": 1}, CAMPOS)
    with pytest.raises(ConfiguracionInvalida) as e:
        raise ConfiguracionInvalida(errores)
    assert e.value.errores == errores and isinstance(e.value, ValueError)
    assert "`otra`: clave desconocida" in str(e.value)
