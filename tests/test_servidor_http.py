"""La puerta HTTP (hito B4), llamada con el cliente de pruebas de Starlette: la aplicación en memoria, sin red.

Lo que se fija: cada operación de la tabla responde por su ruta, lo mismo que la api; los rechazos son «problem
details» con el estado que dice OpenConta (400, 413, 421, 422, 404, 500); y las tres puertas —CLI, MCP y HTTP— dan el
mismo documento y el mismo diagnóstico.
"""
from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from contaperu import api  # noqa: E402
from contaperu.puertas import servidor_http  # noqa: E402
from util import GOLDEN, XML, imputando  # noqa: E402

# Desde la 3.0 la cuenta es del comprobante: los documentos de estas pruebas la traen con `imputando`.
CONFIG = {"usa_centros_costo": False}
LIBRO = {"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA S.A.C.", "periodo": "202601", "tipo": "venta"}


def _cliente(base: str = "http://localhost:8080", **opciones) -> TestClient:
    return TestClient(servidor_http.crear_app(**opciones), base_url=base, raise_server_exceptions=False)


def _golden(nombre: str = "compras_202601.json") -> dict:
    return imputando(json.loads((GOLDEN / nombre).read_text(encoding="utf-8")), "659999")


def _es_problema(respuesta, estado: int, clave: str) -> None:
    assert respuesta.status_code == estado, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    cuerpo = respuesta.json()
    assert cuerpo["status"] == estado and cuerpo["clave"] == clave and cuerpo["type"] == "about:blank"


def test_la_salud_y_el_contrato():
    cliente = _cliente()
    salud = cliente.get("/salud")
    assert salud.status_code == 200 and salud.json() == {"estado": "ok", "motor": api.__version__,
                                                          "open_accounting": api.OPEN_ACCOUNTING}
    assert cliente.get("/openconta.json").json() == api.contrato_openconta()


@pytest.mark.parametrize("op", [op for op in api.OPERACIONES if op.metodo == "GET"], ids=lambda op: op.nombre)
def test_cada_consulta_de_la_tabla_responde_lo_mismo_que_la_api(op):
    respuesta = _cliente().get(op.ruta)
    assert respuesta.status_code == 200 and respuesta.json() == op.funcion()


def test_una_consulta_con_parametros_los_lee_de_la_url():
    respuesta = _cliente().get("/v1/configuracion", params={"driver": "contasis"})
    assert respuesta.json() == api.describir_configuracion("contasis")


@pytest.mark.parametrize("driver", ["concar", "contasis", "csv", "sire"])
def test_exportar_da_lo_mismo_que_la_api(driver):
    documento = _golden()
    respuesta = _cliente().post("/v1/exportar", json={"documento": documento, "driver": driver, "configuracion": CONFIG})
    esperado = api.exportar(documento, driver=driver, configuracion=CONFIG)
    obtenido = respuesta.json()
    assert respuesta.status_code == 200
    if driver in ("concar", "contasis"):         # el .xlsx lleva la hora en que se escribió: se compara lo demás
        obtenido.pop("contenido_base64"), esperado.pop("contenido_base64")
    assert obtenido == esperado


def test_un_rechazo_del_motor_es_un_422_con_su_clave():
    documento = _golden()
    # El documento trae su cuenta y no su centro, y CONCAR exige el centro donde la cuenta lo lleva.
    respuesta = _cliente().post("/v1/exportar", json={"documento": documento, "driver": "concar",
                                                     "configuracion": {}})
    _es_problema(respuesta, 422, "sin_centro")
    sin_libro = _cliente().post("/v1/revisar", json={"documento": {"comprobantes": []}})
    _es_problema(sin_libro, 422, "documento_invalido")


@pytest.mark.parametrize("cuerpo,motivo", [
    ({"documento": {}}, "le falta driver"),
    ({"documento": {}, "driver": "csv", "sobra": 1}, "no recibe sobra"),
    ({"documento": "no es un objeto", "driver": "csv"}, "`documento` tiene que ser object"),
    ({"documento": {}, "driver": "csv", "incluir_observados": "sí"}, "`incluir_observados` tiene que ser boolean"),
])
def test_los_parametros_que_no_cuadran_son_422(cuerpo, motivo):
    respuesta = _cliente().post("/v1/exportar", json=cuerpo)
    _es_problema(respuesta, 422, "parametros_invalidos")
    assert motivo in respuesta.json()["detail"]


@pytest.mark.parametrize("contenido", [b"esto no es json", b"[1, 2, 3]", b"", b"\xff\xfe"])
def test_un_cuerpo_que_no_es_un_objeto_json_es_400(contenido):
    respuesta = _cliente().post("/v1/cuadrar", content=contenido, headers={"content-type": "application/json"})
    _es_problema(respuesta, 400, "cuerpo_mal_formado")


def test_un_cuerpo_demasiado_grande_es_413():
    cliente = _cliente(maximo_peticion=1000)
    _es_problema(cliente.post("/v1/cuadrar", content=b"{" + b" " * 2000 + b"}"), 413, "peticion_demasiado_grande")
    assert servidor_http.MAXIMO_PETICION == 10 * 1024 * 1024


def test_main_arranca_uvicorn_con_los_topes_de_conexiones(monkeypatch):
    """Sin tope, un servidor sin autenticación deja que cualquiera acumule trabajo: `main` le pasa a uvicorn cuántas
    peticiones atiende a la vez y cuánto espera una conexión inactiva (`puertas/comun.py`)."""
    uvicorn = pytest.importorskip("uvicorn")
    from contaperu.puertas import comun

    llamada: dict = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **opciones: llamada.update(opciones))
    assert servidor_http.main(["--puerto", "9999"]) == 0
    assert llamada["limit_concurrency"] == comun.MAXIMO_CONEXIONES > 0
    assert llamada["timeout_keep_alive"] == comun.ESPERA_INACTIVA > 0
    assert (llamada["host"], llamada["port"]) == ("127.0.0.1", 9999)


def test_un_host_que_no_se_declaro_es_421():
    _es_problema(_cliente("http://ataque.ejemplo.com").get("/salud"), 421, "host_no_permitido")
    publico = _cliente("https://contaperu.ejemplo.com", dominios=["contaperu.ejemplo.com"])
    assert publico.get("/salud").status_code == 200
    assert _cliente("http://127.0.0.1:9999").get("/salud").status_code == 200


def test_un_error_que_no_es_del_motor_es_500_sin_detalle(monkeypatch):
    from contaperu.api import operaciones

    def revienta(lineas):
        raise RuntimeError("C:/ruta/interna/secreta")

    monkeypatch.setattr(operaciones, "cuadrar", revienta)
    respuesta = _cliente().post("/v1/cuadrar", json={"lineas": []})
    _es_problema(respuesta, 500, "error_interno")
    assert "secreta" not in respuesta.text


def test_una_ruta_o_un_metodo_que_no_existen():
    _es_problema(_cliente().get("/v1/no_existe"), 404, "ruta_desconocida")
    _es_problema(_cliente().get("/v1/exportar"), 405, "metodo_no_permitido")


def test_las_tres_puertas_dan_el_mismo_documento_y_el_mismo_diagnostico(tmp_path):
    """La CLI, el MCP y HTTP son adaptadores de la misma api: el mismo XML da el mismo documento, y el mismo mes, el mismo
    diagnóstico."""
    pytest.importorskip("mcp")
    from contaperu.puertas import cli
    from contaperu.puertas.servidor_mcp import mcp

    fuente = XML / "20131312955-01-F001-123.xml"
    contenido = fuente.read_text(encoding="utf-8")
    por_http = _cliente().post("/v1/leer_xml", json={"contenido": contenido, "libro": LIBRO}).json()
    por_mcp = json.loads(asyncio.run(
        mcp.call_tool("leer_xml_ubl", {"contenido": contenido, "libro": LIBRO})).content[0].text)
    assert por_http == por_mcp == api.leer_xml(contenido, LIBRO)

    destino = tmp_path / "cli.json"
    cli.main(["generar", "--tipo", "venta", "--ruc", LIBRO["ruc"], "--razon", LIBRO["razon_social"],
              "--periodo", LIBRO["periodo"], "--salida", str(tmp_path / "s"), "--json", str(destino), str(fuente)])
    por_cli = json.loads(destino.read_text(encoding="utf-8"))
    por_http.pop("_lectura")
    for documento in (por_cli, por_http):       # la procedencia es de la puerta: la CLI sabe el nombre del archivo
        for comprobante in documento["comprobantes"]:
            comprobante["archivo_nombre"] = ""
    assert por_cli == por_http

    documento = _golden()
    diagnostico_http = _cliente().post("/v1/diagnosticar", json={"documento": documento, "driver": "concar",
                                                                 "configuracion": CONFIG}).json()
    diagnostico_mcp = json.loads(asyncio.run(mcp.call_tool("diagnosticar", {
        "documento": documento, "configuracion": CONFIG, "driver": "concar"})).content[0].text)
    assert diagnostico_http == diagnostico_mcp == api.diagnosticar(documento, driver="concar", configuracion=CONFIG)
