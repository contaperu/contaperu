"""El servidor MCP, llamado por el protocolo.

Los tests corren las herramientas con `asyncio.run` en vez de con un plugin async: el objetivo
es comprobar que la capa MCP expone bien lo que hay debajo, no ejercitar asyncio.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import contaperu
from contaperu.puertas.servidor_mcp import LOCALES, mcp, seguridad

from util import XML

DOCUMENTO = {
    "open_accounting": "0.3",
    "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
              "periodo": "202608", "tipo": "compra"},
    "comprobantes": [{
        "tipo_cp": "01", "serie": "E001", "numero": "871", "fecha_emision": "2026-08-10",
        "fecha_vencimiento": "2026-08-27", "contraparte_doc": "20602222226",
        "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "4200", "igv": "756",
        "total": "4956", "concepto": "SERVICIO DE TRANSPORTE", "id_externo": "fila-871",
        "detraccion": {"codigo": "027", "porcentaje": 4},
    }],
}

# La cuenta y el centro del comprobante de ejemplo llegan aparte, en la imputación (open-accounting 0.3).
IMPUTACION = {"fila-871": {"cuenta_contable": "659999", "centro_costo": "CC-64"}}


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


def test_estan_las_once_herramientas():
    """El conjunto EXACTO, no un `in`: una herramienta que se cuela sin querer tambien es un fallo.

    Quien conecta esto a su Claude ve esta lista y nada mas; anadir una es una decision, y este
    test es donde se declara.
    """
    nombres = {t.name for t in asyncio.run(mcp.list_tools())}
    assert nombres == {
        "configuracion_por_defecto", "validar_comprobantes", "validar_partida_doble",
        "generar_asiento", "exportar", "leer_xml_ubl", "leer_propuesta_sire",
        "adaptar_pcge2026", "normalizar_detracciones", "buscar_cuenta_pcge", "diagnosticar",
    }


def test_diagnosticar_por_el_protocolo():
    """Un agente pregunta que falta ANTES de exportar, y la respuesta ya viene por serie-numero."""
    listo = llamar("diagnosticar", documento=DOCUMENTO, imputacion=IMPUTACION)
    assert listo["listo_para_exportar"] is True and listo["saldrian"] == ["E001-871"]
    assert listo["detracciones_pendientes"][0]["serie_numero"] == "E001-871"
    assert listo["sub_diarios"]["10"]["empieza_en"] == 1
    r = llamar("diagnosticar", documento=DOCUMENTO, imputacion={"fila-871": {"centro_costo": "CC-64"}})
    assert r["listo_para_exportar"] is False and r["faltantes"]["sin_cuenta"] == ["E001-871"]
    assert r["por_que_no"] == ["1 sin cuenta contable"]
    # Y a quién pedírselo (0.8.0): la cuenta la pone el contador.
    assert r["que_falta"] == [{"motivo": "sin_cuenta", "texto": "sin cuenta contable",
                               "comprobantes": ["E001-871"], "pedir_a": "contador"}]
    assert r["exige"] == ["centro_costo", "cuenta_contable", "moneda", "tipo_cp"]


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
    assert uris == {"contaperu://estandar/open-accounting", "contaperu://catalogos/sunat",
                    "contaperu://drivers", "contaperu://catalogos/pcge2026", "contaperu://configuracion"}
    esquema = json.loads(leer_recurso("contaperu://estandar/open-accounting"))
    assert esquema["title"] == "open-accounting"
    catalogos = json.loads(leer_recurso("contaperu://catalogos/sunat"))
    assert catalogos["tipos_comprobante"]["01"] == "Factura"
    drivers = json.loads(leer_recurso("contaperu://drivers"))
    assert set(drivers) == {"sire", "concar", "csv", "contasis"}
    assert drivers["concar"]["tipo"] == "archivo" and drivers["sire"]["tipo"] == "texto"
    assert drivers["sire"]["familia"] == "registro" and drivers["csv"]["familia"] == "asiento"
    assert drivers["contasis"]["configurable"] is True and drivers["sire"]["configurable"] is False
    configuracion = json.loads(leer_recurso("contaperu://configuracion"))
    assert set(configuracion["sistemas"]) == {"concar", "contasis", "csv"}
    assert [c["columna"] for c in configuracion["sistemas"]["contasis"]["columnas"]["centro_costo"]] == [
        "centro_costo", "centro_costo_2"]
    pcge = json.loads(leer_recurso("contaperu://catalogos/pcge2026"))
    assert "PCGE 2026" in pcge["fuente"] and len(pcge["cuentas"]) > 1500
    assert pcge["cuentas"]["706"]["nombre"] == "Descuentos concedidos por pronto pago"


def test_generar_asiento_por_el_protocolo():
    r = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION)
    assert [ln["cuenta"] for ln in r["asiento"]] == ["659999", "401111", "421201", "421201", "421203"]
    assert r["_asiento"]["cuadre"]["cuadra"] is True


def test_validar_comprobantes_devuelve_el_documento_revisado():
    r = llamar("validar_comprobantes", documento=DOCUMENTO)
    assert r["_revision"]["comprobantes"] == 1 and r["_revision"]["con_error"] == 0
    assert r["comprobantes"][0]["estado"] == "ok"


def test_generar_asiento_con_la_seccion_de_su_sistema():
    """`generar_asiento` aplica la sección del sistema de asientos que se le diga: las columnas que elige para el
    centro deciden los anexos de las líneas, como en su archivo. Uno que no arma asientos se dice."""
    solo_m = {"concar": {"columnas": {"centro_costo": ["centro_costo"]}}}
    concar = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION, configuracion=solo_m)
    assert not any(ln.get("anexo_auxiliar") for ln in concar["asiento"])
    csv = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION, configuracion=solo_m, driver="csv")
    assert [ln.get("anexo_auxiliar") for ln in csv["asiento"] if ln["rol"] == "tercero"] == ["CC-64"]
    with pytest.raises(Exception, match="no arma asientos"):
        llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION, driver="contasis")


def test_la_partida_doble_se_puede_comprobar_sola():
    asiento = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION)["asiento"]
    assert llamar("validar_partida_doble", asiento=asiento)["cuadra"] is True
    asiento[0]["importe"] = "1.00"
    assert llamar("validar_partida_doble", asiento=asiento)["cuadra"] is False


def test_exportar_a_concar_devuelve_el_excel_COMO_ARCHIVO():
    """El Excel tiene que llegar como archivo, no como una tira de base64 dentro del JSON.

    Es la diferencia entre que el cliente lo ofrezca para guardar y que lo enseñe como un muro
    de letras: hace falta el recurso incrustado con su `blob` y su `mimeType`.
    """
    r, adjuntos = exportar(documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)
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
    r, adjuntos = exportar(documento=DOCUMENTO, driver="csv", imputacion=IMPUTACION)
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


def test_buscar_una_cuenta_del_pcge_por_el_protocolo():
    """La herramienta que le da a un modelo de lenguaje contra que contrastar la cuenta que propone.

    Va por `call_tool` a proposito: dentro del servidor conviven DOS `cargar` —el de la tabla de
    adaptacion y el del catalogo— y llamar al que no era devuelve algo con la forma equivocada sin
    reventar. Solo se ve mirando lo que sale por el protocolo.
    """
    r = llamar("buscar_cuenta_pcge", codigo="603201")
    assert "PCGE 2026" in r["fuente"]
    # No esta en la norma y NO es un error: cada empresa abre sus divisionarias.
    assert r["cuenta"]["codigo"] == "6032" and r["cuenta"]["exacta"] is False

    r = llamar("buscar_cuenta_pcge", codigo="706")
    assert r["cuenta"]["exacta"] is True
    assert r["cuenta"]["nombre"] == "Descuentos concedidos por pronto pago"

    r = llamar("buscar_cuenta_pcge", texto="pronto pago")
    codigos = {c["codigo"] for c in r["encontradas"]}
    assert {"605", "706"} <= codigos          # el descuento obtenido y el concedido

    with pytest.raises(Exception, match="texto|codigo"):
        llamar("buscar_cuenta_pcge")


def test_un_codigo_que_no_existe_ni_por_su_elemento_no_resuelve():
    """`99999` no es una divisionaria de nadie: el elemento 9 llega a 97, asi que esta mal escrito."""
    r = llamar("buscar_cuenta_pcge", codigo="99999")
    assert r["cuenta"] is None


def test_el_pcge_avisa_de_que_no_tiene_tabla():
    asiento = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION)["asiento"]
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
        llamar("generar_asiento", documento={"open_accounting": "0.3", "comprobantes": []})


def test_un_comprobante_con_error_bloquea_la_exportacion():
    doc = json.loads(json.dumps(DOCUMENTO))
    doc["comprobantes"][0]["total"] = "9999"          # deja de cuadrar con base + IGV
    with pytest.raises(Exception, match="bloquean|observaciones"):
        exportar(documento=doc, driver="concar", imputacion=IMPUTACION)
    forzado, adjuntos = exportar(documento=doc, driver="concar", incluir_observados=True, imputacion=IMPUTACION)
    assert forzado["archivo"].endswith(".xlsx") and len(adjuntos) == 1


def test_la_imputacion_llega_por_el_protocolo():
    """Las decisiones contables de cada comprobante llegan aparte del documento, por su `id_externo`, en las tres
    herramientas que arman, revisan o exportan el asiento."""
    documento = json.loads(json.dumps(DOCUMENTO))
    documento["comprobantes"][0]["id_externo"] = "fila-871"
    imputacion = {"fila-871": {"cuenta_contable": "636301", "cuenta_tercero": "469901", "centro_costo": "CC-64"}}
    r = llamar("generar_asiento", documento=documento, imputacion=imputacion)
    # La cuenta del total manda también en la línea que le descuenta la detracción al proveedor.
    assert [ln["cuenta"] for ln in r["asiento"]] == ["636301", "401111", "469901", "469901", "421203"]

    corto = {"fila-871": {"reparto": [{"importe": "100", "cuenta_contable": "636301", "centro_costo": "CC-64"}]}}
    d = llamar("diagnosticar", documento=documento, imputacion=corto)
    assert d["faltantes"]["reparto_que_no_cuadra"] == ["E001-871"] and d["listo_para_exportar"] is False

    resumen, _ = exportar(documento=documento, driver="csv", imputacion=imputacion)
    assert ";636301;D;" in resumen["texto"]
