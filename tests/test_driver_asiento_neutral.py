"""El driver open-accounting: el asiento para los ERP que vienen, sin el vocabulario de ningún sistema legacy.

La promesa (John, 15-sep-2026): la contabilidad es la misma que la de CONCAR —cuentas, sentidos, importes y roles, en
el mismo orden—, y lo único que cambia es el vocabulario: sin siglas, sin sub-diarios, sin correlativos y sin el
documento comodín de la detracción.
"""
from __future__ import annotations

import base64
import json
import types

import pytest

from contaperu import api
from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from contaperu.drivers import contrato, asiento_neutral
from test_caracterizacion import IMPUTACION_CASOS
from util import GOLDEN


def casos() -> dict:
    return json.loads((GOLDEN / "casos_202608.json").read_text(encoding="utf-8"))


def contabilidad(lineas: list[dict]) -> list[tuple]:
    return [(linea["cuenta"], linea["debe_haber"], linea["importe"], linea.get("rol")) for linea in lineas]


def test_la_contabilidad_es_la_misma_que_la_de_concar():
    """Soles y dólares, notas, detracción, honorarios, boleta, reparto y extemporáneo: el mismo asiento para los dos."""
    neutral = api.generar_asiento(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)
    concar = api.generar_asiento(casos(), driver="concar", imputacion=IMPUTACION_CASOS)
    assert neutral["asiento"] and contabilidad(neutral["asiento"]) == contabilidad(concar["asiento"])
    assert neutral["_asiento"]["cuadre"] == concar["_asiento"]["cuadre"]


def test_las_lineas_no_llevan_vocabulario_legacy():
    lineas = api.generar_asiento(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)["asiento"]
    assert all(not {"sub_diario", "correlativo"} & set(linea) for linea in lineas)
    assert all(linea["documento"].get("tipo_cp") and "tipo" not in linea["documento"] for linea in lineas)
    assert all("tipo" not in (linea.get("referencia") or {}) for linea in lineas)
    detraccion = [linea for linea in lineas if linea["rol"] == "detraccion"]
    assert detraccion, "el golden trae una factura con detracción"
    assert all(linea["documento"]["serie_numero"] != "999999999" for linea in detraccion)
    assert all(linea["detraccion"]["codigo"] and "codigo_interno" not in linea["detraccion"] for linea in detraccion)


def test_un_tipo_sin_sigla_no_detiene_a_un_erp():
    """Un ERP no necesita la sigla de CONCAR: le basta el código SUNAT. Al CSV, que habla legacy, sí lo detiene."""
    sin_sigla = {"csv": {"tipos": {"01": {"sigla": ""}}}}
    with pytest.raises(api.SinSigla):
        api.generar_asiento(casos(), driver="csv", configuracion=sin_sigla, imputacion=IMPUTACION_CASOS)
    assert api.generar_asiento(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)["asiento"]


def test_exporta_el_documento_del_estandar_y_valida_su_esquema():
    jsonschema = pytest.importorskip("jsonschema")
    respuesta = api.exportar(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)
    documento = json.loads(base64.b64decode(respuesta["contenido_base64"]))
    jsonschema.Draft202012Validator(api.esquema_open_accounting()).validate(documento)
    assert documento["asiento"] and respuesta["resumen"]["sub_diarios"] == {}
    assert respuesta["_exportacion"]["huella"] and respuesta["_exportacion"]["comprobantes"][0]["lineas"]


def test_el_archivo_se_basta_solo_para_no_repetir_un_comprobante():
    """El archivo lleva `_exportacion` en su raíz (3.1), y esto es lo que hace que sirva a quien NO llama al motor.

    Hasta la 3.1 el documento tenía tres claves y la huella vivía solo en la respuesta del API, así que quien
    recibiera el JSON —por correo, en una carpeta— se quedaba sin la clave con la que reconocer lo que ya había
    importado. `INTEGRAR.md` le pide a un ERP justamente eso, «la identidad y la huella de cada comprobante como
    clave para no repetir», y por la vía del archivo era imposible de seguir.

    Y lo que va dentro es LO MISMO que dice el API, no una versión reducida: las dos salen de
    `asiento.exportacion_de`."""
    respuesta = api.exportar(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)
    documento = json.loads(base64.b64decode(respuesta["contenido_base64"]))

    dentro = documento["_exportacion"]
    assert dentro["huella"] == respuesta["_exportacion"]["huella"]
    assert dentro["comprobantes"] == respuesta["_exportacion"]["comprobantes"]
    assert dentro["driver"] == "asiento_neutral" and dentro["motor"]

    # Cada comprobante: su identidad, su tramo y la huella de ese tramo. Los tramos parten las líneas enteras.
    tramos = [c["lineas"] for c in dentro["comprobantes"]]
    assert tramos[0][0] == 0 and tramos[-1][1] == len(documento["asiento"])
    assert all(a[1] == b[0] for a, b in zip(tramos, tramos[1:])), "los tramos dejan hueco o se solapan"
    assert all(c["identidad"]["ruc"] and c["huella"] for c in dentro["comprobantes"])


def test_lo_que_el_archivo_no_puede_saber_no_se_inventa():
    """`fecha` la pone quien llama a `exportar` y `archivo` es el nombre del propio archivo: ninguna de las dos es
    un hecho del asiento, así que el documento no las lleva. Decirlo con un test evita que alguien las añada
    «por simetría» con la respuesta del API."""
    documento = json.loads(base64.b64decode(
        api.exportar(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)["contenido_base64"]))
    assert set(documento["_exportacion"]) == {"driver", "motor", "huella", "comprobantes"}


def test_el_diagnostico_de_un_erp_no_mira_vocabulario_legacy():
    diagnostico = api.diagnosticar(casos(), driver="asiento_neutral", imputacion=IMPUTACION_CASOS)
    assert diagnostico["listo_para_exportar"] is True
    assert diagnostico["exige"] == ["cuenta_contable"] and diagnostico["sub_diarios"] == {}
    assert "sin_sigla" not in diagnostico["faltantes"] and "sin_codigo_de_moneda" not in diagnostico["faltantes"]


def test_un_erp_no_tiene_seccion_propia_en_la_configuracion():
    """Lee lo general, que es contabilidad; no tiene siglas ni sub-diarios que configurar."""
    assert api.errores_de_configuracion({"asiento_neutral": {}}) == [
        "`asiento_neutral` no tiene sección: ese sistema no tiene nada propio que configurar, solo lo general"]
    assert "asiento_neutral" not in api.configuracion_por_defecto()


def test_el_contrato_de_un_driver_neutral():
    assert contrato.incumplimientos(asiento_neutral) == []
    assert (contrato.vocabulario(asiento_neutral), contrato.grupo(asiento_neutral)) == ("neutral", "erp")
    assert contrato.exige(asiento_neutral) == {"cuenta_contable"}
    assert api.drivers_disponibles()["asiento_neutral"]["vocabulario"] == "neutral"
    assert api.drivers_disponibles()["concar"]["vocabulario"] == "legacy"

    def copia(**cambios) -> types.ModuleType:
        falso = types.ModuleType("falso")
        falso.__dict__.update({k: v for k, v in vars(asiento_neutral).items() if not k.startswith("__")})
        falso.__dict__.update(cambios)
        return falso

    assert any("canal es `intercambio`" in p for p in contrato.incumplimientos(copia(CANAL="legacy")))
    assert any("no existe" in p for p in contrato.incumplimientos(copia(VOCABULARIO="otro")))
    legacy = contrato.incumplimientos(copia(CONFIGURACION=CONFIGURACION_DEL_ASIENTO))
    assert any("no declara vocabulario legacy" in p for p in legacy)
    assert any("código de la moneda" in p for p in contrato.incumplimientos(copia(EXIGE=frozenset({"moneda"}))))
