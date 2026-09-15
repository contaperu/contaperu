"""OpenConta, el contrato de la puerta HTTP (hito B3): generado desde la tabla, versionado byte a byte, válido como
OpenAPI 3.1 y fiel a lo que responde el motor —las respuestas reales validan contra su salida y los documentos de
ejemplo, contra su entrada—.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from contaperu import api
from contaperu.api import openconta, tabla
from util import GOLDEN, XML

VERSIONADO = Path(__file__).resolve().parents[1] / "contaperu" / "api" / "openconta.json"
CONFIG = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}


def _contrato() -> dict:
    return json.loads(VERSIONADO.read_text(encoding="utf-8"))


def _golden(nombre: str = "compras_202601.json") -> dict:
    return json.loads((GOLDEN / nombre).read_text(encoding="utf-8"))


def _validar(componente: str, instancia) -> None:
    """Valida contra un esquema de `components.schemas`, resolviendo sus `$ref` dentro del propio contrato."""
    Draft202012Validator({**_contrato(), "$ref": f"#/components/schemas/{componente}"}).validate(instancia)


def _referencias(valor):
    if isinstance(valor, dict):
        for clave, v in valor.items():
            if clave == "$ref":
                yield v
            else:
                yield from _referencias(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _referencias(v)


def test_regenerarlo_no_cambia_ni_un_byte():
    assert openconta.texto().encode("utf-8") == VERSIONADO.read_bytes(), (
        "el contrato no está al día: python herramientas/generar_openconta.py")
    assert api.contrato_openconta() == _contrato()


def test_es_openapi_3_1_y_cada_operacion_de_la_tabla_tiene_su_ruta():
    contrato = _contrato()
    assert contrato["openapi"] == "3.1.0" and "servers" not in contrato
    assert contrato["info"]["title"] == "OpenConta" and contrato["info"]["version"] == api.__version__
    assert contrato["info"]["x-open-accounting"] == api.OPEN_ACCOUNTING
    rutas = {(ruta, metodo) for ruta, metodos in contrato["paths"].items() for metodo in metodos}
    assert rutas == {(op.ruta, op.metodo.lower()) for op in api.OPERACIONES} | {("/salud", "get"),
                                                                                ("/openconta.json", "get")}
    for op in api.OPERACIONES:
        assert contrato["paths"][op.ruta][op.metodo.lower()]["operationId"] == op.nombre


def test_cada_referencia_resuelve_dentro_del_contrato():
    contrato = _contrato()
    for referencia in set(_referencias(contrato)):
        assert referencia.startswith("#/"), referencia
        nodo = contrato
        for parte in referencia[2:].split("/"):
            nodo = nodo[parte]


def test_cada_esquema_es_json_schema_2020_12():
    for esquema in _contrato()["components"]["schemas"].values():
        Draft202012Validator.check_schema(esquema)


def test_valida_como_openapi_3_1():
    """Con `openapi-spec-validator` (extra `dev`), la validación oficial del formato."""
    validador = pytest.importorskip("openapi_spec_validator")
    validador.validate(_contrato())


def test_la_tabla_apunta_al_estandar_por_su_id():
    assert tabla.ESTANDAR == api.esquema_open_accounting()["$id"]
    for nombre in openconta.ESQUEMAS:
        from contaperu import _datos
        assert _datos.leer_esquema(nombre)["$id"] == f"{tabla.BASE_ESQUEMAS}{nombre}.schema.json"


@pytest.mark.parametrize("driver", ["concar", "contasis", "csv", "sire", "open_accounting"])
def test_el_diagnostico_y_la_exportacion_reales_validan(driver):
    documento = _golden()
    _validar("diagnostico", api.diagnosticar(documento, driver=driver, configuracion=CONFIG))
    _validar("exportacion", api.exportar(documento, driver=driver, configuracion=CONFIG, fecha="2026-09-14"))


def test_el_diagnostico_con_la_configuracion_invalida_tambien_valida():
    """Hito B2: la otra forma de la respuesta de `diagnosticar`, la de una configuración que no se puede aplicar."""
    diagnostico = api.diagnosticar(_golden(), driver="concar", configuracion={"clave_que_no_existe": 1})
    assert diagnostico["errores_de_configuracion"]
    _validar("diagnostico", diagnostico)
    assert api.esquema_diagnostico() == json.loads(
        (Path(api.__file__).parent / "esquemas" / "diagnostico.schema.json").read_text(encoding="utf-8"))


def test_las_demas_respuestas_reales_validan():
    documento = _golden()
    asiento = api.generar_asiento(documento, driver="csv", configuracion=CONFIG)
    _validar("asiento", asiento)
    _validar("cuadre", api.cuadrar(asiento["asiento"]))
    _validar("adaptacion_pcge", api.adaptar_pcge(asiento["asiento"]))
    _validar("documento_anotado", api.revisar(documento, claves_previas=[["01", "F001", "1", "20131312955"]]))
    _validar("documento_anotado", api.normalizar_detracciones(documento))
    libro = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA S.A.C.", "periodo": "202601", "tipo": "venta"}
    _validar("documento_anotado", api.leer_xml((XML / "20131312955-01-F001-123.xml").read_text(encoding="utf-8"), libro))
    _validar("cuenta_pcge", api.buscar_cuenta_pcge(codigo="603201", texto="suministros"))
    _validar("drivers", api.drivers_disponibles())
    _validar("catalogos_sunat", api.catalogos_sunat())
    _validar("configuracion", api.configuracion_por_defecto())
    _validar("problema", api.problema(api.ErroresBloqueantes([{"indice": 0}])))


def test_los_documentos_de_ejemplo_validan_como_cuerpos():
    documento = dict(_golden(), open_accounting=api.OPEN_ACCOUNTING)     # un cuerpo lleva el documento completo
    _validar("exportar_entrada", {"documento": documento, "driver": "concar", "configuracion": CONFIG,
                                  "imputacion": {"fila-1": {"cuenta_contable": "636301"}},
                                  "claves_previas": [["01", "F001", "1", "20131312955"]], "fecha": "2026-09-14"})
    ventas = dict(_golden("ventas_202512.json"), open_accounting=api.OPEN_ACCOUNTING)
    _validar("diagnosticar_entrada", {"documento": ventas, "driver": "sire"})
    _validar("cuadrar_entrada", {"lineas": api.generar_asiento(documento, driver="csv", configuracion=CONFIG)["asiento"]})
    with pytest.raises(ValidationError, match="driver"):
        _validar("exportar_entrada", {"documento": documento})
    with pytest.raises(ValidationError):
        _validar("exportar_entrada", {"documento": documento, "driver": "concar", "sobra": True})
