"""El servidor MCP, llamado por el protocolo.

Los tests corren las herramientas con `asyncio.run` en vez de con un plugin async: el objetivo
es comprobar que la capa MCP expone bien lo que hay debajo, no ejercitar asyncio.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import contaperu
from contaperu import api
from contaperu.puertas.servidor_mcp import LOCALES, mcp, seguridad

from util import XML

DOCUMENTO = {
    "open_accounting": "1.0",
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
    """El JSON de una llamada que sale bien.

    Desde la 1.3.0 toda herramienta contesta un `CallToolResult`, como ya hacia `exportar`: el resultado
    en el primer bloque de texto, y con `isError` el rechazo (ver `rechazo`).
    """
    resultado = asyncio.run(mcp.call_tool(herramienta, argumentos))
    assert not resultado.isError, resultado.content[0].text
    return json.loads(resultado.content[0].text)


def rechazo(herramienta: str, **argumentos) -> dict:
    """El «problem details» de una llamada que se niega: su `clave` estable, su `detail` y su `status`."""
    resultado = asyncio.run(mcp.call_tool(herramienta, argumentos))
    assert resultado.isError, "se esperaba un rechazo y la llamada salio bien"
    return json.loads(resultado.content[0].text)


def exportar(**argumentos):
    """`exportar` no devuelve solo JSON: devuelve el resumen y el archivo adjunto.

    Se separan aquí para que cada test diga cuál de las dos cosas está mirando.
    """
    resultado = asyncio.run(mcp.call_tool("exportar", argumentos))
    assert not resultado.isError, resultado.content[0].text
    resumen, *adjuntos = resultado.content
    return json.loads(resumen.text), [a.resource for a in adjuntos]


def leer_recurso(uri: str) -> str:
    contenidos = list(asyncio.run(mcp.read_resource(uri)))
    return contenidos[0].content


def test_estan_las_doce_herramientas():
    """El conjunto EXACTO, no un `in`: una herramienta que se cuela sin querer tambien es un fallo.

    Quien conecta esto a su Claude ve esta lista y nada mas; anadir una es una decision, y este
    test es donde se declara.
    """
    nombres = {t.name for t in asyncio.run(mcp.list_tools())}
    assert nombres == {
        "configuracion_por_defecto", "validar_comprobantes", "validar_partida_doble",
        "generar_asiento", "exportar", "leer_xml_ubl", "leer_propuesta_sire",
        "adaptar_pcge2026", "normalizar_detracciones", "buscar_cuenta_pcge", "diagnosticar",
        "drivers_disponibles",
    }


def test_diagnosticar_por_el_protocolo():
    """Un agente pregunta que falta ANTES de exportar, y la respuesta ya viene por serie-numero."""
    listo = llamar("diagnosticar", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)
    assert listo["listo_para_exportar"] is True and listo["saldrian"] == ["E001-871"]
    assert listo["detracciones_pendientes"][0]["serie_numero"] == "E001-871"
    assert listo["sub_diarios"]["10"]["empieza_en"] == 1
    r = llamar("diagnosticar", documento=DOCUMENTO, driver="concar",
               imputacion={"fila-871": {"centro_costo": "CC-64"}})
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
                    "contaperu://catalogos/estandar", "contaperu://drivers",
                    "contaperu://catalogos/pcge2026", "contaperu://configuracion",
                    "contaperu://esquemas/diagnostico"}
    esquema = json.loads(leer_recurso("contaperu://estandar/open-accounting"))
    assert esquema["title"] == "open-accounting"
    catalogos = json.loads(leer_recurso("contaperu://catalogos/sunat"))
    assert catalogos["tipos_comprobante"]["01"] == "Factura"
    del_estandar = json.loads(leer_recurso("contaperu://catalogos/estandar"))
    assert del_estandar["clases"]["codigos"]["activo"] and del_estandar["roles"]["version"]
    drivers = json.loads(leer_recurso("contaperu://drivers"))
    assert set(drivers) == {"sire", "concar", "csv", "contasis", "asiento_neutral"}
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
    r = llamar("generar_asiento", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)
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
    concar = llamar("generar_asiento", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION,
                    configuracion=solo_m)
    assert not any(ln.get("anexo_auxiliar") for ln in concar["asiento"])
    csv = llamar("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION, configuracion=solo_m, driver="csv")
    assert [ln.get("anexo_auxiliar") for ln in csv["asiento"] if ln["rol"] == "tercero"] == ["CC-64"]
    negado = rechazo("generar_asiento", documento=DOCUMENTO, imputacion=IMPUTACION, driver="contasis")
    assert negado["clave"] == "valor_invalido" and "no arma asientos" in negado["detail"]


def test_la_partida_doble_se_puede_comprobar_sola():
    asiento = llamar("generar_asiento", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)["asiento"]
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

    negado = rechazo("buscar_cuenta_pcge")
    assert negado["clave"] == "documento_invalido" and "texto" in negado["detail"]


def test_un_codigo_que_no_existe_ni_por_su_elemento_no_resuelve():
    """`99999` no es una divisionaria de nadie: el elemento 9 llega a 97, asi que esta mal escrito."""
    r = llamar("buscar_cuenta_pcge", codigo="99999")
    assert r["cuenta"] is None


def test_el_pcge_avisa_de_que_no_tiene_tabla():
    asiento = llamar("generar_asiento", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)["asiento"]
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
    negado = rechazo("generar_asiento", documento={"open_accounting": "1.0", "comprobantes": []}, driver="concar")
    assert negado["clave"] == "documento_invalido" and "libro" in negado["detail"]


def test_un_comprobante_con_error_bloquea_la_exportacion():
    doc = json.loads(json.dumps(DOCUMENTO))
    doc["comprobantes"][0]["total"] = "9999"          # deja de cuadrar con base + IGV
    negado = rechazo("exportar", documento=doc, driver="concar", imputacion=IMPUTACION)
    assert negado["clave"] == "documento_invalido" and "bloquean" in negado["detail"]
    # Cuales son no lo dice aqui, y a proposito: eso lo contesta `diagnosticar`, que es la que hay que llamar antes.
    assert "incluir_observados" in negado["detail"]
    forzado, adjuntos = exportar(documento=doc, driver="concar", incluir_observados=True, imputacion=IMPUTACION)
    assert forzado["archivo"].endswith(".xlsx") and len(adjuntos) == 1


def test_la_imputacion_llega_por_el_protocolo():
    """Las decisiones contables de cada comprobante llegan aparte del documento, por su `id_externo`, en las tres
    herramientas que arman, revisan o exportan el asiento."""
    documento = json.loads(json.dumps(DOCUMENTO))
    documento["comprobantes"][0]["id_externo"] = "fila-871"
    imputacion = {"fila-871": {"cuenta_contable": "636301", "cuenta_tercero": "469901", "centro_costo": "CC-64"}}
    r = llamar("generar_asiento", documento=documento, driver="concar", imputacion=imputacion)
    # La cuenta del total manda también en la línea que le descuenta la detracción al proveedor.
    assert [ln["cuenta"] for ln in r["asiento"]] == ["636301", "401111", "469901", "469901", "421203"]

    corto = {"fila-871": {"reparto": [{"importe": "100", "cuenta_contable": "636301", "centro_costo": "CC-64"}]}}
    d = llamar("diagnosticar", documento=documento, driver="concar", imputacion=corto)
    assert d["faltantes"]["reparto_que_no_cuadra"] == ["E001-871"] and d["listo_para_exportar"] is False

    resumen, _ = exportar(documento=documento, driver="csv", imputacion=imputacion)
    assert ";636301;D;" in resumen["texto"]


def test_un_pdf_por_el_protocolo_queda_pendiente_de_leer():
    """Hito 0.7: un agente que manda el PDF de la factura en vez del XML recibe «pendiente de leer», no un error."""
    import base64

    libro = DOCUMENTO["libro"]
    leido = llamar("leer_xml_ubl", contenido=base64.b64encode(b"%PDF-1.7\n1 0 obj").decode(), libro=libro,
                   es_base64=True)
    assert leido["_lectura"]["pendientes_de_leer"] == 1 and leido["_lectura"]["errores"] == []


def test_cada_herramienta_se_anuncia_de_solo_lectura_y_sin_salir_a_ningun_sitio():
    """Hito 0.2: `readOnlyHint` y `openWorldHint` en las doce, recorriendo lo que ve el cliente."""
    herramientas = asyncio.run(mcp.list_tools())
    assert len(herramientas) == 12
    for herramienta in herramientas:
        anotaciones = herramienta.annotations
        assert anotaciones is not None and anotaciones.readOnlyHint is True, herramienta.name
        assert anotaciones.openWorldHint is False, herramienta.name


def test_el_destino_no_se_supone():
    """El sistema contable de un contribuyente es suyo: la puerta MCP no puede elegirlo por él.

    Hasta la 1.3.0 las tres herramientas que van hacia un destino traian `driver="concar"` de fabrica,
    y eran las unicas de las tres puertas que lo hacian: la api lo exige (`tests/test_api.py`), el
    contrato OpenConta lo declara obligatorio y la linea de comandos lo ensena en su `--help`. Un agente
    que olvidara el parametro le daba un Excel de CONCAR a un contribuyente de CONTASIS, y eso no se nota
    hasta que el archivo ya esta importado.
    """
    por_nombre = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for nombre in ("generar_asiento", "diagnosticar", "exportar"):
        entrada = por_nombre[nombre].inputSchema
        assert "driver" in entrada["required"], f"{nombre}: el driver se supone"
        assert "default" not in entrada["properties"]["driver"], f"{nombre}: el driver trae un destino de fabrica"


def test_sin_destino_la_llamada_se_niega():
    """Y se niega antes de tocar nada, no generando el archivo del sistema equivocado."""
    # Este sí sigue siendo una excepción del SDK, y está bien: un argumento que el `inputSchema` prohíbe no llega
    # al motor, así que no hay rechazo del motor que contar. Lo que el motor niega sale con su clave (ver abajo).
    with pytest.raises(Exception, match="driver"):
        asyncio.run(mcp.call_tool("diagnosticar", {"documento": DOCUMENTO, "imputacion": IMPUTACION}))


def test_los_destinos_se_pueden_preguntar_llamando_y_no_solo_leyendo():
    """`drivers_disponibles` sale por las dos vias, y es la unica que lo hace.

    Un recurso lo lee quien quiere: en MCP los recursos los gobierna la aplicacion, asi que puede
    ofrecerselos al modelo o dejarlos como adjuntos que elige la persona. Desde que `driver` se
    declara (1.3.0), saber que destinos hay dejo de poder depender de esa decision del cliente.
    """
    por_nombre = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert "drivers_disponibles" in por_nombre
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert "contaperu://drivers" in uris, "el recurso sigue ahi: quitarlo romperia a quien ya lo lee"

    llamado = llamar("drivers_disponibles")
    leido = json.loads(leer_recurso("contaperu://drivers"))
    assert llamado == leido, "las dos vias tienen que decir lo mismo"
    assert set(llamado) == {"sire", "concar", "csv", "contasis", "asiento_neutral"}
    # La diferencia que un agente necesita saber ANTES de elegir: el centro de costo lo pide CONCAR y no el CSV.
    assert "centro_costo" in llamado["concar"]["exige"]
    assert "centro_costo" not in llamado["csv"]["exige"]


# Los dos unicos parametros que el MCP llama distinto que la api, y a proposito: para un agente esa lista de
# diccionarios es «el asiento», no «las lineas». Declarados a la vista, como las toleradas de `test_capas.py`.
RENOMBRA = {"validar_partida_doble": {"lineas": "asiento"}, "adaptar_pcge2026": {"lineas": "asiento"}}


def test_la_puerta_mcp_recibe_lo_mismo_que_la_http():
    """Las dos puertas salen de la misma tabla, y lo que reciben tiene que salir de ahi tambien.

    La causa de la unica divergencia contable que ha tenido este servidor —tres herramientas suponiendo
    CONCAR— fue que el MCP escribe sus parametros a mano, en anotaciones de Python, mientras la puerta
    HTTP los deriva de `api/tabla.py`. Dos fuentes para un mismo contrato divergen solas; este test es la
    unica razon por la que no volveran a hacerlo sin que nadie lo vea.
    """
    por_nombre = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for op in api.OPERACIONES:
        if not op.herramienta:
            continue
        renombra = RENOMBRA.get(op.herramienta, {})
        entrada = op.entrada
        esperadas = {renombra.get(n, n) for n in entrada["properties"]}
        obligatorias = {renombra.get(n, n) for n in entrada["required"]}
        real = por_nombre[op.herramienta].inputSchema
        assert set(real["properties"]) == esperadas, f"{op.herramienta}: recibe otra cosa que POST {op.ruta}"
        assert set(real.get("required", [])) == obligatorias, f"{op.herramienta}: exige otra cosa que POST {op.ruta}"


def test_una_clave_previa_admite_el_numero_como_numero():
    """Por HTTP el esquema acepta `string`, `integer` o `null`, y el motor tambien; por MCP solo texto.

    El peligro no es el rechazo: es lo que hace un agente cuando se lo encuentra. Quitar las claves previas
    para que la llamada pase deja pasar un comprobante ya anotado en otro periodo, y eso SUNAT lo rechaza.
    """
    previa = ["01", "E001", 871, "20602222226"]          # el numero como numero, no como texto
    r = llamar("validar_comprobantes", documento=DOCUMENTO, claves_previas=[previa])
    codigos = [o["codigo"] for o in r["comprobantes"][0]["observaciones"]]
    assert "DUPLICADO_PERIODO_ANTERIOR" in codigos


def test_la_imputacion_se_comprueba_al_revisar():
    """`api.revisar` la acepta y `POST /v1/revisar` tambien: una llave huerfana sale aqui, no al exportar."""
    negado = rechazo("validar_comprobantes", documento=DOCUMENTO,
                     imputacion={"fila-inventada": {"cuenta_contable": "659999"}})
    assert negado["clave"] == "documento_invalido" and "fila-inventada" in negado["detail"]


def test_un_error_que_no_es_del_motor_no_ensena_su_texto(monkeypatch):
    """El espejo de `test_api.py`, que exigia esto mismo de la puerta HTTP y no de esta.

    Un error imprevisto puede llevar pegada una ruta del servidor o un dato interno. Por HTTP se
    enmascara desde siempre; por MCP salia entero, y es la puerta que esta publicada sin autenticacion.
    """
    monkeypatch.setattr("contaperu.api.diagnosticar",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("C:/ruta/interna/secreta")))
    negado = rechazo("diagnosticar", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)
    assert negado["status"] == 500 and negado["clave"] == "error_interno"
    assert "secreta" not in json.dumps(negado), "una ruta interna no sale por una puerta publica"


def test_ninguna_herramienta_declara_esquema_de_salida():
    """Lo que devuelven se describe en su descripcion y, para `diagnosticar`, en su recurso.

    Es la decision que ya explica el recurso `contaperu://esquemas/diagnostico`: el SDK no deja declarar
    un `outputSchema` sin cambiar lo que responde. Queda escrita aqui para que un cambio del SDK que
    empiece a inventarse uno se vea en la bateria y no en produccion.
    """
    for herramienta in asyncio.run(mcp.list_tools()):
        assert herramienta.outputSchema is None, herramienta.name
