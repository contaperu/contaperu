"""El servidor MCP, llamado por el protocolo.

Los tests corren las herramientas con `asyncio.run` en vez de con un plugin async: el objetivo
es comprobar que la capa MCP expone bien lo que hay debajo, no ejercitar asyncio.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import contaperu
from contaperu.servidor_mcp import LOCALES, mcp, seguridad

from util import XML

DOCUMENTO = {
    "pe_ledger": "0.1",
    "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
              "periodo": "202608", "tipo": "compra"},
    "comprobantes": [{
        "tipo_cp": "01", "serie": "E001", "numero": "871", "fecha_emision": "2026-08-10",
        "fecha_vencimiento": "2026-08-27", "contraparte_doc": "20602222226",
        "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "4200", "igv": "756",
        "total": "4956", "concepto": "SERVICIO DE TRANSPORTE", "cuenta_contable": "659999",
        "centro_costo": "CC-64", "detraccion": {"codigo": "027", "porcentaje": 4},
    }],
}


def llamar(herramienta: str, **argumentos):
    bloques = asyncio.run(mcp.call_tool(herramienta, argumentos))
    return json.loads(bloques[0].text)


def exportar(**argumentos):
    """`exportar` no devuelve solo JSON: devuelve el resumen y el archivo adjunto.

    Se separan aquí para que cada test diga cuál de las dos cosas está mirando.
    """
    resultado = asyncio.run(mcp.call_tool("exportar", argumentos))
    resumen, *adjuntos = resultado.content
    return json.loads(resumen.text), [a.resource for a in adjuntos]


def leer_recurso(uri: str) -> str:
    contenidos = list(asyncio.run(mcp.read_resource(uri)))
    return contenidos[0].content


def test_estan_las_nueve_herramientas():
    nombres = {t.name for t in asyncio.run(mcp.list_tools())}
    assert nombres == {
        "configuracion_por_defecto", "validar_comprobantes", "validar_partida_doble",
        "generar_asiento", "exportar", "leer_xml_ubl", "leer_propuesta_sire",
        "adaptar_pcge2026", "normalizar_detracciones",
    }


def test_el_servidor_se_presenta_con_SU_version():
    """Sin ponersela a mano, FastMCP saluda con la version del SDK: «contaperu 1.30.0»."""
    assert mcp._mcp_server.version == contaperu.__version__


def test_publicarlo_detras_de_un_proxy_exige_declarar_el_dominio():
    """Sin declararlo, el SDK responde 421 a todo lo que llegue por el nombre publico.

    Paso al levantarlo por primera vez: el proxy bien, el certificado bien, y aun asi ni una
    peticion entraba desde internet, porque el servidor solo se reconocia como «localhost».
    """
    s = seguridad(["contaperu.ejemplo.com"])
    assert "contaperu.ejemplo.com" in s.allowed_hosts
    assert "https://contaperu.ejemplo.com" in s.allowed_origins
    assert "localhost:*" in s.allowed_hosts       # y localhost sigue valiendo para comprobar
    assert seguridad([]).allowed_hosts == LOCALES


def test_cada_herramienta_se_explica_sola():
    """Un agente elige la herramienta por su descripción: ninguna puede ir sin una."""
    for t in asyncio.run(mcp.list_tools()):
        assert t.description and len(t.description) > 80, t.name
        assert t.inputSchema["type"] == "object"


def test_los_recursos_son_legibles():
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert uris == {"contaperu://estandar/pe-ledger", "contaperu://catalogos/sunat",
                    "contaperu://drivers"}
    esquema = json.loads(leer_recurso("contaperu://estandar/pe-ledger"))
    assert esquema["title"] == "pe-ledger"
    catalogos = json.loads(leer_recurso("contaperu://catalogos/sunat"))
    assert catalogos["tipos_comprobante"]["01"] == "Factura"
    drivers = json.loads(leer_recurso("contaperu://drivers"))
    assert set(drivers) == {"sire", "concar", "csv"}
    assert drivers["concar"]["tipo"] == "archivo" and drivers["sire"]["tipo"] == "texto"


def test_generar_asiento_por_el_protocolo():
    r = llamar("generar_asiento", documento=DOCUMENTO)
    assert [ln["cuenta"] for ln in r["asiento"]] == ["659999", "401111", "421201", "421201", "421203"]
    assert r["_asiento"]["cuadre"]["cuadra"] is True


def test_validar_comprobantes_devuelve_el_documento_revisado():
    r = llamar("validar_comprobantes", documento=DOCUMENTO)
    assert r["_revision"]["total"] == 1 and r["_revision"]["con_error"] == 0
    assert r["comprobantes"][0]["estado"] == "ok"


def test_la_partida_doble_se_puede_comprobar_sola():
    asiento = llamar("generar_asiento", documento=DOCUMENTO)["asiento"]
    assert llamar("validar_partida_doble", asiento=asiento)["cuadra"] is True
    asiento[0]["importe"] = "1.00"
    assert llamar("validar_partida_doble", asiento=asiento)["cuadra"] is False


def test_exportar_a_concar_devuelve_el_excel_COMO_ARCHIVO():
    """El Excel tiene que llegar como archivo, no como una tira de base64 dentro del JSON.

    Es la diferencia entre que el cliente lo ofrezca para guardar y que lo enseñe como un muro
    de letras: hace falta el recurso incrustado con su `blob` y su `mimeType`.
    """
    r, adjuntos = exportar(documento=DOCUMENTO, driver="concar")
    assert r["archivo"].endswith(".xlsx") and r["formato"] == "concar_xlsx"
    assert r["resumen"]["debe"] == r["resumen"]["haber"] == "5154.00"
    assert "contenido_base64" not in r, "los bytes van en el adjunto, no repetidos en el JSON"

    excel, = adjuntos
    assert excel.mimeType == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert str(excel.uri).endswith(r["archivo"])
    import base64
    import io

    import openpyxl
    crudo = base64.b64decode(excel.blob)
    assert crudo[:2] == b"PK"                                   # es un .xlsx de verdad
    assert openpyxl.load_workbook(io.BytesIO(crudo)).active.max_row > 1


def test_exportar_al_sire_devuelve_texto_y_su_zip_adjunto():
    r, adjuntos = exportar(documento=DOCUMENTO, driver="sire")
    assert r["archivo"].endswith(".TXT") and r["texto"].count("|") > 30
    assert "zip_base64" not in r and r["archivo_zip"].endswith(".zip")
    zip_, = adjuntos
    assert zip_.mimeType == "application/zip"
    import base64
    assert base64.b64decode(zip_.blob)[:2] == b"PK"


def test_exportar_a_csv_es_legible():
    r, adjuntos = exportar(documento=DOCUMENTO, driver="csv")
    assert r["texto"].splitlines()[0].startswith("sub_diario;correlativo")
    csv, = adjuntos
    assert csv.mimeType == "text/csv"                # sin el `; charset=utf-8` del content-type


def test_leer_un_xml_de_sunat():
    xml = (XML / "20131312955-01-F001-123.xml").read_text(encoding="utf-8")
    r = llamar("leer_xml_ubl", contenido=xml,
               libro={"ruc": "20131312955", "razon_social": "EMISOR DE PRUEBA SAC",
                      "periodo": "202601", "tipo": "venta"})
    assert len(r["comprobantes"]) == 1 and r["comprobantes"][0]["serie"] == "F001"
    assert r["comprobantes"][0]["origen"] == "xml"


def test_el_pcge_avisa_de_que_no_tiene_tabla():
    asiento = llamar("generar_asiento", documento=DOCUMENTO)["asiento"]
    r = llamar("adaptar_pcge2026", asiento=asiento)
    assert r["informe"]["sin_tabla"] is True and r["informe"]["cambios"] == 0
    assert r["asiento"] == asiento


def test_normalizar_detracciones_descarta_lo_que_no_reconoce():
    doc = json.loads(json.dumps(DOCUMENTO))
    doc["comprobantes"][0]["detraccion"] = {"codigo": "000", "porcentaje": 3}
    r = llamar("normalizar_detracciones", documento=doc)
    assert r["_detracciones"]["descartadas"] == 1
    assert r["comprobantes"][0]["detraccion"] is None
    assert "027" in r["_detracciones"]["codigos_reconocidos"]


def test_un_documento_sin_libro_falla_diciendo_por_que():
    with pytest.raises(Exception, match="libro"):
        llamar("generar_asiento", documento={"pe_ledger": "0.1", "comprobantes": []})


def test_un_comprobante_con_error_bloquea_la_exportacion():
    doc = json.loads(json.dumps(DOCUMENTO))
    doc["comprobantes"][0]["total"] = "9999"          # deja de cuadrar con base + IGV
    with pytest.raises(Exception, match="bloquean|observaciones"):
        exportar(documento=doc, driver="concar")
    forzado, adjuntos = exportar(documento=doc, driver="concar", incluir_observados=True)
    assert forzado["archivo"].endswith(".xlsx") and len(adjuntos) == 1
