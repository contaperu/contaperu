"""El servidor MCP, llamado por el protocolo.

Los tests corren las herramientas con `asyncio.run` en vez de con un plugin async: el objetivo
es comprobar que la capa MCP expone bien lo que hay debajo, no ejercitar asyncio.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

import contaperu
from contaperu import api
from contaperu.puertas.servidor_mcp import LOCALES, mcp, seguridad

from util import XML

DOCUMENTO = {
    "open_accounting": "4.0",
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


def test_estan_las_dieciocho_herramientas():
    """El conjunto EXACTO, no un `in`: una herramienta que se cuela sin querer tambien es un fallo.

    Quien conecta esto a su Claude ve esta lista y nada mas; anadir una es una decision, y este
    test es donde se declara.
    """
    nombres = {t.name for t in asyncio.run(mcp.list_tools())}
    assert nombres == {
        "configuracion_por_defecto", "validar_comprobantes", "validar_partida_doble",
        "estado_de_cuenta",
        # 15.13.0: lo que un pago tiene que cancelar de cada compra, con la regla del asiento.
        "por_pagar",
        "generar_asiento", "exportar", "leer_xml_ubl", "leer_propuesta_sire",
        "adaptar_pcge2026", "normalizar_detracciones", "buscar_cuenta_pcge", "diagnosticar",
        "drivers_disponibles", "validar_cuentas_bancarias", "revisar_tesoreria",
        # 3.4.0: cuanto es un libro y en que cuentas cayo. Ninguna pide destino.
        "resumen", "por_cuenta",
    }


def test_diagnosticar_por_el_protocolo():
    """Un agente pregunta que falta ANTES de exportar, y la respuesta ya viene por serie-numero."""
    listo = llamar("diagnosticar", documento=DOCUMENTO, driver="concar", imputacion=IMPUTACION)
    assert listo["listo_para_exportar"] is True and listo["saldrian"] == ["E001-871"]
    assert listo["detracciones_pendientes"][0]["serie_numero"] == "E001-871"
    assert listo["sub_diarios"]["10"]["empieza_en"] == 1
    # Sin cuenta en la imputación falta, y desde la 3.0 no hay ninguna de la empresa que la supla.
    r = llamar("diagnosticar", documento=DOCUMENTO, driver="concar",
               imputacion={"fila-871": {"centro_costo": "CC-64"}})
    assert r["listo_para_exportar"] is False and r["faltantes"]["sin_cuenta"] == ["E001-871"]
    assert r["por_que_no"] == ["1 sin cuenta contable"]
    # Y a quién pedírselo (0.8.0): la cuenta la pone el contador.
    assert r["que_falta"] == [{"motivo": "sin_cuenta", "texto": "sin cuenta contable",
                               "comprobantes": ["E001-871"], "pedir_a": "contador"}]
    assert r["exige"] == ["centro_costo", "cuenta_contable", "detraccion", "moneda", "tipo_cp"]


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


def test_las_reglas_del_dominio_no_nombran_ninguna_herramienta():
    """`REGLAS` existe para que otro servidor MCP se las lleve, y eso solo funciona si no habla de ESTE.

    `INTEGRAR.md` le pide a todo integrador que se traiga lo que este servidor le dice al agente; hasta la
    3.4 era un solo texto que empezaba por «llama a `leer_xml_ubl`», que en su servidor no existe —y
    prometerle a un modelo una herramienta que no puede llamar es peor que no decirle nada—. Sin este
    test, la próxima regla útil vuelve a nacer con un nombre de herramienta pegado y nadie lo nota hasta
    que alguien la copia.
    """
    nombres = {t.name for t in asyncio.run(mcp.list_tools())}
    citadas = sorted(n for n in nombres if n in api.REGLAS)
    assert not citadas, (f"las REGLAS nombran herramientas de este servidor: {citadas}. "
                         f"El puntero va en `CAMINO`; la regla, sin nombre propio.")
    # Y siguen siendo la mitad de lo que el servidor anuncia: partirlo no cambió lo que dice.
    assert api.REGLAS in mcp.instructions and api.CAMINO in mcp.instructions
    for uri in (str(r.uri) for r in asyncio.run(mcp.list_resources())):
        assert uri not in api.REGLAS, f"las REGLAS citan el recurso {uri} de este servidor"


# Lo que Claude Code lee de las instrucciones de un servidor MCP: los primeros 2 048 caracteres, y nada más (medido el
# 21-nov-2026). Se corta en unidades UTF-16, que son las de una cadena de JavaScript; en castellano coinciden con los
# caracteres, y se cuenta así para que una letra fuera del plano básico no las separe sin que se vea.
RECORTE_DEL_CLIENTE = 2048


def lo_que_lee_el_cliente(texto: str) -> str:
    return texto.encode("utf-16-le")[:2 * RECORTE_DEL_CLIENTE].decode("utf-16-le", errors="ignore")


def test_todas_las_reglas_caben_en_lo_que_lee_el_cliente():
    """Una regla que el cliente corta no existe para su modelo.

    Hasta la 15.14 las instrucciones medían 3 832 caracteres y las reglas empezaban en el 831, detrás del camino de
    las herramientas: un desarrollador que conectaba este servidor a su Claude Code recibía las cuatro primeras y la
    mitad de la quinta —la del no domiciliado—, y las del plan de cuentas, la imputación, las claves previas y la
    cuenta que no se inventa no le llegaban. Desde la 15.15 van antes del camino y caben enteras, y esto es el
    trinquete: una regla nueva paga su sitio acortando otra, y lo que se pase se ve aquí y no en la conversación de
    alguien.
    """
    leido = lo_que_lee_el_cliente(mcp.instructions)
    assert leido.count("Reglas que conviene tener claras") == 1, "el encabezado de las reglas tiene que llegar, y una vez"
    for ambito, reglas in api.REGLAS_POR_CLAVE.items():
        for clave, texto in reglas.items():
            assert texto in leido, (f"la regla {ambito}.{clave} no cabe en los {RECORTE_DEL_CLIENTE} caracteres que "
                                    f"lee el cliente: las instrucciones miden {len(mcp.instructions)}")


def test_las_reglas_son_la_union_de_las_que_tienen_nombre():
    """`REGLAS` sigue existiendo, y es exactamente lo que `REGLAS_POR_CLAVE` tiene, en su orden.

    Si alguien escribiera una regla suelta en `REGLAS` sin darle clave, quien se trae las del documento por su
    nombre no la vería nunca; y una con clave que no llegara a `REGLAS` faltaría en el servidor del motor.
    """
    assert set(api.REGLAS_POR_CLAVE) == {"documento", "llamada"}
    vinietas = [linea[2:] for linea in api.REGLAS.splitlines() if linea.startswith("- ")]
    con_nombre = [texto for reglas in api.REGLAS_POR_CLAVE.values() for texto in reglas.values()]
    assert vinietas == con_nombre
    assert api.REGLAS.splitlines()[0] == "Reglas que conviene tener claras antes de armar un documento:"
    assert len(api.REGLAS.splitlines()) == 1 + len(con_nombre), "en `REGLAS` hay texto que no es de ninguna regla"


def test_las_reglas_del_documento_no_nombran_nada_de_la_llamada():
    """Las del documento son para quien arma un documento y llama al motor de OTRA forma.

    Las importa un conector que no tiene `imputacion`, ni `claves_previas`, ni `configuracion`, ni el catálogo
    `catalogos_sunat`: si una de ellas nombra un argumento, una operación o un destino de este motor, ese conector le
    habla a su modelo de algo que no existe. Lo que sí pueden nombrar son los campos del estándar —`codigo` es el de la
    detracción aunque también sea un argumento de `buscar_cuenta_pcge`—, así que se descuentan.
    """
    from contaperu.api.tabla import PARAMETROS

    esquema = json.loads(leer_recurso("contaperu://estandar/open-accounting"))
    campos: set[str] = set()

    def recorrer(nodo) -> None:
        if isinstance(nodo, dict):
            if isinstance(nodo.get("properties"), dict):
                campos.update(nodo["properties"])
            for valor in nodo.values():
                recorrer(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                recorrer(valor)

    recorrer(esquema)
    de_la_llamada = ((set(PARAMETROS) | {op.nombre for op in api.OPERACIONES}
                      | {op.herramienta for op in api.OPERACIONES if op.herramienta}
                      | set(api.drivers_disponibles())) - campos)
    for clave, texto in api.REGLAS_POR_CLAVE["documento"].items():
        nombrados = set(re.findall(r"`([^`]+)`", texto)) & de_la_llamada
        assert not nombrados, f"la regla documento.{clave} nombra {sorted(nombrados)}, que son de la llamada"


def test_las_secciones_que_se_nombran_son_las_que_se_configuran():
    """La lista de secciones se escribía a mano y se quedó en `concar`, `csv` y `contasis` con seis secciones vivas.

    Se compara con lo que la configuración valida de verdad —`describir_configuracion`—, en los dos sitios donde se
    nombra: la regla de la configuración y la descripción de `configuracion_por_defecto`.
    """
    secciones = set(api.describir_configuracion()["sistemas"])
    assert secciones >= {"concar", "csv", "contasis", "starsoft", "ple", "ple_plan"}
    descripcion = {t.name: t.description for t in asyncio.run(mcp.list_tools())}["configuracion_por_defecto"]
    for donde, texto in (("la regla llamada.configuracion", api.REGLAS_POR_CLAVE["llamada"]["configuracion"]),
                         ("la descripción de `configuracion_por_defecto`", descripcion)):
        nombradas = set(re.findall(r"`([a-z_]+)`", texto)) & set(api.drivers_disponibles())
        assert nombradas == secciones, f"{donde} nombra {sorted(nombradas)} y se configuran {sorted(secciones)}"


def test_exportar_nombra_cada_destino():
    """La lista de destinos de `exportar` va por canal y con lo que entrega cada uno, así que se escribe a mano.

    Escrita a mano envejece: le faltaba `sire_no_domiciliados` desde la 15.6. Esto la ata a los drivers que hay.
    """
    descripcion = {t.name: t.description for t in asyncio.run(mcp.list_tools())}["exportar"]
    faltan = sorted(d for d in api.drivers_disponibles() if f"`{d}` —" not in descripcion)
    assert not faltan, f"la descripción de `exportar` no presenta estos destinos: {faltan}"


def rama_de_texto(esquema: dict) -> dict:
    """La parte de un esquema que describe el texto: él mismo, o su rama `string` si es opcional (`anyOf` con null)."""
    for rama in esquema.get("anyOf", [esquema]):
        if rama.get("type") == "string":
            return rama
    return {}


def test_cada_parametro_dice_lo_que_dice_la_tabla():
    """Los 52 parámetros de las 18 herramientas llegaban con un nombre y un tipo, y la tabla ya los describía.

    Se compara con `op.entrada`, que es el esquema con que la puerta HTTP y el contrato publican la MISMA operación: la
    descripción de cada parámetro, y su `enum` y su `format` en la rama del texto. Y `driver`, que la tabla no cierra
    porque el contrato no sabe qué drivers de terceros habrá, lleva los que este servidor tiene al arrancar.
    """
    por_nombre = {t.name: t for t in asyncio.run(mcp.list_tools())}
    vistos = 0
    for op in api.OPERACIONES:
        if not op.herramienta:
            continue
        renombra = RENOMBRA.get(op.herramienta, {})
        for nombre, de_la_tabla in op.entrada["properties"].items():
            publicado = por_nombre[op.herramienta].inputSchema["properties"][renombra.get(nombre, nombre)]
            donde = f"{op.herramienta}.{nombre}"
            assert publicado.get("description") == de_la_tabla["description"], donde
            rama = rama_de_texto(publicado)
            for clave in ("enum", "format"):
                if clave in de_la_tabla:
                    assert rama.get(clave) == de_la_tabla[clave], f"{donde}: su `{clave}` no es el de la tabla"
            if nombre == "driver":
                assert rama["enum"] == list(api.drivers_disponibles()), donde
            vistos += 1
    assert vistos == 52


def test_solo_se_cierran_los_parametros_que_tienen_lista():
    """Un `enum` es una promesa de que no hay más valores, y solo dos parámetros la pueden hacer.

    `driver` —los destinos de este servidor— y `agrupar_por`. Los catálogos de SUNAT siguen abiertos aunque el motor
    los conozca: un tipo de comprobante o un código de detracción que SUNAT añada tiene que poder llegar al motor y
    que sea él quien diga qué hace con él, no el esquema de una herramienta quien lo rechace antes.
    """
    cerrados = {nombre for t in asyncio.run(mcp.list_tools()) for nombre, esquema in t.inputSchema["properties"].items()
                if "enum" in rama_de_texto(esquema)}
    assert cerrados == {"driver", "agrupar_por"}


def test_los_recursos_son_legibles():
    uris = {str(r.uri) for r in asyncio.run(mcp.list_resources())}
    assert uris == {"contaperu://estandar/open-accounting", "contaperu://catalogos/sunat",
                    "contaperu://catalogos/estandar", "contaperu://drivers",
                    "contaperu://catalogos/pcge2026", "contaperu://configuracion",
                    "contaperu://esquemas/diagnostico", "contaperu://catalogos/sire-api",
                    "contaperu://catalogos/sire-campos", "contaperu://catalogos/ple-campos",
                    "contaperu://catalogos/regimenes", "contaperu://catalogos/vencimientos",
                    "contaperu://campos/comprobante", "contaperu://catalogos/observaciones"}
    esquema = json.loads(leer_recurso("contaperu://estandar/open-accounting"))
    # Qué significa cada observación (15.16.0): el mismo catálogo que `api`, con lo que cambia según el origen.
    observaciones = json.loads(leer_recurso("contaperu://catalogos/observaciones"))
    assert observaciones == api.catalogo_de_observaciones()
    assert observaciones["IGV_NO_CUADRA"]["nivel_por_origen"] == {"sire": "aviso"}
    assert esquema["title"] == "open-accounting"
    catalogos = json.loads(leer_recurso("contaperu://catalogos/sunat"))
    assert catalogos["tipos_comprobante"]["01"] == "Factura"
    regimenes = json.loads(leer_recurso("contaperu://catalogos/regimenes"))["regimenes"]
    assert regimenes["especial"]["pago_a_cuenta"]["tasa"] == "1.5"
    assert regimenes["especial"]["libros_obligatorios"]["codigos_ple"] == ["080100", "140100"]
    vencimientos = json.loads(leer_recurso("contaperu://catalogos/vencimientos"))["anios"]["2026"]
    assert vencimientos["declaracion"]["202609"]["3"] == "2026-10-20"
    assert vencimientos["atraso_registros"]["202609"]["3"] == "2026-10-19"
    del_estandar = json.loads(leer_recurso("contaperu://catalogos/estandar"))
    assert del_estandar["clases"]["codigos"]["activo"] and del_estandar["roles"]["version"]
    # El canal del SIRE: datos sobre una API ajena, no un cliente. Lo que se comprueba es que
    # siga diciendo lo que más caro cuesta descubrir a mano.
    # Quién escribe cada campo: lo que una puerta de entrada lee para saber qué acepta de quien dicta.
    campos = json.loads(leer_recurso("contaperu://campos/comprobante"))
    assert "total" in campos["documento"] and "estado" in campos["revision"]
    assert "origen" in campos["sistema"] and campos["obligatorios"] == ["tipo_cp", "fecha_emision", "total"]
    canal = json.loads(leer_recurso("contaperu://catalogos/sire-api"))
    assert canal["libros"]["080000"]["nombre"] == "RCE"
    # Los dos manuales se contradicen aquí, y el dato es por libro a propósito.
    assert canal["libros"]["080000"]["cod_tipo_archivo"]["csv"] == 1
    assert canal["libros"]["140000"]["cod_tipo_archivo"]["excel"] == 1
    # RVIE y RCE no comparten ruta: cruzarlas da 500 de nginx, no 404.
    aceptar = canal["operaciones"]["propuesta_aceptar"]["ruta_por_libro"]
    assert aceptar["080000"] != aceptar["140000"]
    # Y el techo: no existe por API, y quien integre debe saberlo antes de prometerlo.
    assert "generar_el_registro" in canal["no_existe_por_api"]

    drivers = json.loads(leer_recurso("contaperu://drivers"))
    assert set(drivers) == {"sire", "sire_no_domiciliados", "concar", "csv", "contasis", "starsoft",
                            "asiento_contable", "ple", "ple_plan"}
    assert drivers["concar"]["tipo"] == "archivo" and drivers["sire"]["tipo"] == "texto"
    assert drivers["sire"]["familia"] == "registro" and drivers["csv"]["familia"] == "asiento"
    assert drivers["contasis"]["configurable"] is True and drivers["sire"]["configurable"] is False
    configuracion = json.loads(leer_recurso("contaperu://configuracion"))
    assert set(configuracion["sistemas"]) == {"concar", "contasis", "csv", "starsoft", "ple", "ple_plan"}
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
    from contaperu.drivers.kit.rol import rol_de
    assert [ln.get("anexo_auxiliar") for ln in csv["asiento"]
            if rol_de(ln, "compra") == "tercero"] == ["CC-64"]
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
    negado = rechazo("generar_asiento", documento={"open_accounting": "4.0", "comprobantes": []}, driver="concar")
    assert negado["clave"] == "documento_invalido" and "libro" in negado["detail"]


def test_un_rechazo_dice_cuales_comprobantes_por_el_protocolo():
    """El agente que recibe un «1 comprobante(s) sin cuenta contable» sabe cuál (15.16.0): con su nombre, sus partes y
    el `id_externo` con que lo mandó. Es la misma `api.problema` de la puerta HTTP."""
    documento = json.loads(json.dumps(DOCUMENTO))
    documento["comprobantes"][0]["id_externo"] = "fila-871"
    negado = rechazo("exportar", documento=documento, driver="concar",
                     imputacion={"fila-871": {"centro_costo": "CC-64"}})
    assert negado["clave"] == "sin_cuenta"
    assert negado["comprobantes"] == [{"comprobante": "01 E001-871", "id_externo": "fila-871",
                                       "partes": {"tipo_cp": "01", "serie": "E001", "numero": "871",
                                                  "contraparte_doc": "20602222226"}}]


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
    """Hito 0.2: `readOnlyHint` y `openWorldHint` en todas, recorriendo lo que ve el cliente."""
    herramientas = asyncio.run(mcp.list_tools())
    assert len(herramientas) == 18
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
    assert set(llamado) == {"sire", "sire_no_domiciliados", "concar", "csv", "contasis", "starsoft",
                            "asiento_contable", "ple", "ple_plan"}
    # La diferencia que un agente necesita saber ANTES de elegir: el centro de costo lo pide CONCAR y no el CSV.
    assert "centro_costo" in llamado["concar"]["exige"]
    assert "centro_costo" not in llamado["csv"]["exige"]


# Los dos unicos parametros que el MCP llama distinto que la api, y a proposito: para un agente esa lista de
# diccionarios es «el asiento», no «las lineas». Declarados a la vista, como las toleradas de `test_capas.py`.
RENOMBRA = {"validar_partida_doble": {"lineas": "asiento"}, "adaptar_pcge2026": {"lineas": "asiento"},
            # `por_cuenta` recibe las líneas de un asiento y las llama como sus dos hermanas del MCP: por
            # HTTP el parámetro se llama `lineas`, que es el nombre de la api.
            "por_cuenta": {"lineas": "asiento"}}


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


def test_el_servidor_solo_admite_stdio_y_http(capsys):
    """`--transporte sse` existio hasta la 1.3.0 y no hacia lo que decia.

    Quedaba fuera del bloque que pone `stateless_http` y la defensa del `Host`, asi que `--dominio` se
    ignoraba en silencio y las sesiones se acumulaban. No estaba documentado, no estaba probado, y el
    transporte esta obsoleto en la especificacion desde 2025-03-26. Una opcion publicada que no hace lo
    que promete es peor que no tenerla.
    """
    from contaperu.puertas.servidor_mcp import main

    with pytest.raises(SystemExit):
        main(["--transporte", "sse"])
    error = capsys.readouterr().err
    # Sin atarse a como lo redacta argparse: 3.11 entrecomilla las opciones («choose from 'stdio', 'http'»), 3.12
    # las deja desnudas y 3.13 vuelve a entrecomillarlas. Lo que importa es que rechaza `sse` y dice cuales valen.
    assert "sse" in error and "stdio" in error and "http" in error


def test_servirlo_en_red_es_sin_sesiones_y_con_el_dominio_declarado(monkeypatch):
    """Lo que `main` prepara antes de arrancar, que hasta ahora no comprobaba nadie."""
    from contaperu.puertas import servidor_mcp

    arrancado = {}
    monkeypatch.setattr(servidor_mcp.mcp, "run", lambda transport: arrancado.update(transporte=transport))
    servidor_mcp.main(["--transporte", "http", "--host", "0.0.0.0", "--dominio", "contaperu.ejemplo.com"])
    assert arrancado["transporte"] == "streamable-http"
    assert servidor_mcp.mcp.settings.stateless_http is True, "un anonimo no puede ir acumulando sesiones"
    assert "contaperu.ejemplo.com" in servidor_mcp.mcp.settings.transport_security.allowed_hosts


# --- lo que el agente ve, congelado ------------------------------------------------

PUBLICADO = Path(__file__).resolve().parent / "fixtures" / "mcp" / "publicado.json"


def publicado() -> dict:
    """Lo que este servidor publica: cada herramienta con su descripción, su esquema de entrada y sus
    anotaciones, y cada recurso con su nombre, su descripción y su tipo de contenido."""
    herramientas = asyncio.run(mcp.list_tools())
    recursos = asyncio.run(mcp.list_resources())
    return {
        "herramientas": {h.name: {"descripcion": h.description, "entrada": h.inputSchema,
                                  "anotaciones": h.annotations.model_dump() if h.annotations else None}
                         for h in herramientas},
        "recursos": {str(r.uri): {"nombre": r.name, "descripcion": r.description, "mime": r.mimeType}
                     for r in recursos},
    }


def regenerar() -> None:
    PUBLICADO.parent.mkdir(parents=True, exist_ok=True)
    PUBLICADO.write_bytes((json.dumps(publicado(), ensure_ascii=False, indent=1, sort_keys=True) + "\n")
                          .encode("utf-8"))


def test_lo_que_el_agente_ve_no_cambia_sin_que_se_decida():
    """La superficie del MCP, congelada: los 14 nombres, los 13 recursos, y de cada uno el texto exacto, el
    esquema que el SDK deriva de la firma y sus anotaciones.

    **Es el test que sostiene la 6.2.0**, donde las herramientas dejaron de escribirse a mano y pasaron a
    derivarse de `api.OPERACIONES`: este fixture se capturó ANTES del refactor y pasó después sin cambiar un
    byte, que es la única forma de demostrar que a un cliente no le cambió nada. Lo que vigila desde entonces
    es lo de siempre: que tocar la tabla no mueva en silencio lo que el agente lee.

    Si cambia a propósito —una operación nueva, un texto mejor— se regenera:

        python -c "import sys; sys.path.insert(0, 'tests'); import test_servidor_mcp as t; t.regenerar()"

    Un cambio que NO se quería suele ser una de tres: un parámetro que se renombró en la fachada, un texto de
    `api.textos` que se editó sin querer, o una versión nueva del SDK que escribe el `title` de otra forma.
    El diff lo dice en una línea."""
    congelado = json.loads(PUBLICADO.read_text(encoding="utf-8"))
    hoy = publicado()
    for tipo in ("herramientas", "recursos"):
        assert set(hoy[tipo]) == set(congelado[tipo]), (
            f"cambió el conjunto de {tipo}: faltan {sorted(set(congelado[tipo]) - set(hoy[tipo]))}, "
            f"sobran {sorted(set(hoy[tipo]) - set(congelado[tipo]))}")
    assert hoy == congelado, "lo que el agente ve cambió; si es a propósito, regenera fixtures/mcp/publicado.json"
