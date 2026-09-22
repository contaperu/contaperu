"""El driver STARSOFT, probado por la fachada y contra los casos de los vídeos.

Se prueba por `api.exportar` y `api.diagnosticar`, no por dentro: es como lo usa quien integra el motor, y así
el test sigue valiendo si mañana cambia el reparto entre `proyeccion.py` y `salida.py`.

Los números son los del vídeo de compras —base 929.49, IGV 167.31, total 1096.80, la factura F136-431 del
01-07-2025— con el RUC cambiado por los de prueba. Si una regla del driver deja de cumplirse, aquí se ve en la
celda concreta y no en un total.

Lo que NO se prueba, porque no consta: que STARSOFT acepte el archivo. Eso lo dirá el día que alguien lo
importe, y entonces este archivo gana su prueba de aceptación como la tiene CONTASIS (`test_plantilla_contasis`).
"""
from __future__ import annotations

import base64
import io
import re
import zipfile

import pytest

from contaperu import api
from contaperu.drivers import starsoft

RUC = "20601234567"
PROVEEDOR = "20131312955"
# Los dos tipos de anexo van con su valor de fabrica: 03 proveedores (video de compras), 02 clientes
# (captura de la hoja PLANTILLA de ventas). Se dejan explicitos para que el test diga cual usa cada libro.
CONFIG = {"usa_centros_costo": True,
          "starsoft": {"tipo_anexo_proveedor": "03", "tipo_anexo_cliente": "02"}}


def _compra(**cambios) -> dict:
    comprobante = {"tipo_cp": "01", "serie": "F136", "numero": "431", "fecha_emision": "2025-07-01",
                   "fecha_vencimiento": "2025-07-31", "contraparte_tipo_doc": "6", "contraparte_doc": PROVEEDOR,
                   "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "929.49", "igv": "167.31",
                   "total": "1096.80", "moneda": "PEN", "concepto": "CELULARES", "id_externo": "fila-1"}
    comprobante.update(cambios)
    return {"open_accounting": "1.0",
            "libro": {"ruc": RUC, "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202507", "tipo": "compra"},
            "comprobantes": [comprobante]}


def _venta(**cambios) -> dict:
    doc = _compra(serie="F001", numero="123", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                  base_gravada="93.22", igv="16.78", total="110.00", **cambios)
    doc["libro"]["tipo"] = "venta"
    return doc


def _exportar(documento, config=None, imputacion=None) -> dict:
    return api.exportar(documento, driver="starsoft", configuracion=config or CONFIG,
                        imputacion=imputacion or {"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})


def _texto(r: dict) -> str:
    """El TXT, sacado del ZIP y no de `r["texto"]`: así lo que se prueba es lo que de verdad se descarga."""
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(r["zip_base64"]))) as z:
        return z.read(r["archivo"]).decode("utf-8")


def _filas(documento, config=None, imputacion=None) -> list[dict]:
    """Las filas del archivo, partidas por `|` y con el nombre de su columna.

    El TXT **no lleva cabecera**, así que los nombres salen de `datos.COLUMNAS` — y eso es justo lo que hay que
    comprobar: que cada campo cae en la posición que su columna dice, porque es un formato por POSICIÓN."""
    r = _exportar(documento, config, imputacion)
    columnas = [cabecera for _, cabecera, _ in starsoft.COLUMNAS[documento["libro"]["tipo"]]]
    filas = []
    for linea in _texto(r).split("\r\n"):
        if not linea:
            continue
        campos = linea.split("|")
        assert len(campos) == len(columnas), f"{len(campos)} campos para {len(columnas)} columnas: {linea}"
        filas.append(dict(zip(columnas, campos)))
    return filas


def test_una_compra_sale_con_las_tres_lineas_del_asiento_tipico():
    """El asiento tipo 1 de STARSOFT: gasto al debe, IGV al debe, pasivo al haber.

    Y las tres cuentas son de OCHO digitos, que es como numera STARSOFT. La del gasto llega en la imputacion; las
    otras dos las pone el driver (`datos.CUENTAS_POR_DEFECTO`, 2.5) sin que esta configuracion diga nada de
    cuentas. Hasta entonces este mismo test fijaba `401111` y `421201` —las de CONCAR— dentro de un archivo de
    STARSOFT: el fallo estaba congelado en su propia prueba.

    El ORDEN es el de los ejemplos oficiales —IGV, proveedor, gasto—, que no es el del asiento del motor
    (`datos.ORDEN_DE_LA_COMPRA`, 2.5)."""
    filas = _filas(_compra())
    assert [(f["CTA CONTABLE"], f["DEBE / HABER"], f["IMPORTE"]) for f in filas] == [
        ("40111000", "D", "167.31"), ("42120001", "H", "1096.80"), ("60111000", "D", "929.49")]


def test_las_cuentas_con_las_que_nace_una_empresa_de_starsoft():
    """STARSOFT numera a OCHO digitos y las de fabrica del motor son las del PCGE a seis.

    Se fija la tabla entera —no solo las dos que se ven en el asiento tipico— porque la mitad son DEDUCIDAS del
    patron que ensenan las del manual y no constan en ningun sitio: si alguien las cambia, que sea a proposito.
    Las cuatro del manual van aparte, que es lo unico que se puede afirmar.
    """
    del_manual = {"cxp": "42120001", "igv": "40111000", "clientes": "12120001", "ventas": "70410001"}
    cuentas = starsoft.CUENTAS_POR_DEFECTO
    assert cuentas["cxp"]["PEN"] == del_manual["cxp"]
    assert cuentas["igv"] == del_manual["igv"]
    assert cuentas["clientes"]["PEN"] == del_manual["clientes"]
    assert cuentas["ventas"] == del_manual["ventas"]
    # Las deducidas: la misma cuenta de lo general con el patron de STARSOFT (subcuenta de 4 + correlativo de 4;
    # las de raiz de 5, como el IGV y la renta de 4ta, completan con 3).
    assert cuentas["cxp"]["USD"] == "42120002"
    assert cuentas["cxp_detraccion"] == {"PEN": "42120003", "USD": "42120003"}
    assert cuentas["honorarios"] == {"PEN": "42410001", "USD": "42410002"}
    assert cuentas["retencion_4ta"] == "40172100"
    assert cuentas["clientes"]["USD"] == "12120002"
    # `gasto` NO: en lo general va vacia a proposito (es el comodin 63/65) y el `62010001` del manual es una cuenta
    # de gasto real. De respaldo imputaria a mercaderias, en silencio, toda compra sin cuenta.
    assert "gasto" not in cuentas
    assert api.config_aplicada(driver="starsoft")["cuentas"]["gasto"] == ""


def _con_detraccion(**cambios) -> dict:
    """La misma compra, afecta a detraccion: codigo 027 al 4 % sobre 1096.80 → 43.87."""
    return _compra(detraccion={"codigo": "027", "porcentaje": "4"}, **cambios)


def test_una_compra_con_detraccion_sale_con_las_mismas_tres_filas_que_una_sin_ella():
    """STARSOFT NO asienta la detraccion: la lleva en campos del documento (John, 22-sep-2026, contra el manual).

    En CONCAR el traslado a la cuenta de detracciones son dos lineas mas —el proveedor al debe y 421203 al
    haber—, y hasta la 2.4 este driver las escribia porque proyectaba tal cual lo que el nucleo le daba. El
    manual no las tiene: sus seis ejemplos llevan tres filas por comprobante. El asiento del motor sigue siendo
    el mismo para todos los destinos; lo que cambia es lo que este driver escribe.
    """
    sin, con = _filas(_compra()), _filas(_con_detraccion())
    assert len(sin) == len(con) == 3
    assert [f["CTA CONTABLE"] for f in con] == [f["CTA CONTABLE"] for f in sin] == [
        "40111000", "42120001", "60111000"]
    # Y el archivo cuadra solo con esas tres: lo detraido no mueve cuentas aqui.
    debe = sum(float(f["IMPORTE"]) for f in con if f["DEBE / HABER"] == "D")
    haber = sum(float(f["IMPORTE"]) for f in con if f["DEBE / HABER"] == "H")
    assert debe == haber == 1096.80
    # La cuenta de detracciones NO aparece: es la que se dejo de escribir.
    assert all(f["CTA CONTABLE"] != "42120003" for f in con)


def test_los_campos_de_la_detraccion_van_en_la_fila_del_proveedor():
    """Los del manual: 24 afecto, 25 numero, 26 fecha, 31 codigo, 34 tasa, 35 importe.

    La bandera del 24 va en las TRES filas —es del comprobante, no de la linea—; los otros cinco, solo en la del
    proveedor, como el IGV y su tasa. Y la CONSTANCIA va en blanco a proposito: se deposita despues de exportar,
    «casi pasando el otro mes» (John, 22-sep-2026), asi que quien la conoce es STARSOFT y no nosotros."""
    filas = _filas(_con_detraccion())
    assert [f["DETRACCION"] for f in filas] == ["1", "1", "1"]
    proveedor = filas[1]          # IGV, proveedor, gasto
    assert proveedor["CTA CONTABLE"] == "42120001"
    assert proveedor["CODIGO DETRACCION"] == "027"      # el de SUNAT, no el interno de CONCAR (02702)
    assert proveedor["TASA DETRACCION"] == "4.00"
    # Lo DETRAIDO, que no es el 4 % exacto de 1096.80 (43.872): la detraccion se redondea al sol, y eso lo
    # decide el nucleo, igual para todos los destinos.
    assert proveedor["IMPORTE DETRACCION"] == "44.00"
    assert proveedor["NRO DOC DETRACCION"] == "" and proveedor["FECHA DETRACCION"] == ""
    # Y en las otras dos no van: el codigo vacio, y los dos importes a `0.00`, que es como los ejemplos
    # oficiales dicen «no aplica» en esas columnas.
    for otra in (filas[0], filas[2]):
        assert otra["CODIGO DETRACCION"] == ""
        assert otra["TASA DETRACCION"] == otra["IMPORTE DETRACCION"] == "0.00"


def test_sin_detraccion_la_bandera_va_en_cero_y_sus_importes_tambien():
    """`0.00` y no vacio en las dos columnas de importe, como en los ejemplos oficiales (John, 22-sep-2026)."""
    for f in _filas(_compra()):
        assert f["DETRACCION"] == "0"
        assert f["CODIGO DETRACCION"] == ""
        assert f["TASA DETRACCION"] == f["IMPORTE DETRACCION"] == "0.00"
        assert f["PORC OPE MIXTA"] == f["VALOR CIF"] == "0.00"


def test_el_sub_diario_de_compras_es_el_de_starsoft_y_no_el_de_concar():
    """`04`, no `11`. «El subdiario por defecto para compras es cuatro según el sistema contable» (compras 6:08).

    A DOS digitos y con el cero delante (John, 21-sep-2026): es un codigo, no un numero, como el `03` de ventas."""
    assert {f["SUBDIARIO"] for f in _filas(_compra())} == {"04"}


def test_el_sub_diario_de_ventas_tambien():
    """`03`, no `05` (John, 20-sep-2026)."""
    filas = _filas(_venta(), config={"usa_centros_costo": False},
                   imputacion={"fila-1": {"cuenta_contable": "70410100"}})
    assert {f["SUBDIARIO"] for f in filas} == {"03"}


def test_el_voucher_va_sin_el_mes_pero_con_sus_cuatro_digitos():
    """El motor numera `070001`; STARSOFT empieza en 1 y sigue (compras 6:15), con el ancho del campo.

    Los ceros son el ancho, no adorno: hasta la 2.0 el recorte del mes pasaba por `int()` y salía `1`."""
    assert {f["COMPROBANTE"] for f in _filas(_compra())} == {"0001"}


def test_las_banderas_que_se_saben_van_en_cero_y_no_en_blanco():
    """Las cuatro banderas de la fila dicen `0` y no se callan.

    `DOCUMENTO ANULADO`: un comprobante que entra al registro no está anulado, y afirmarlo es más claro que
    callarlo (John, 21-sep-2026). `IGV POR APLICAR`: `1` seria que el IGV esta PENDIENTE de aplicacion, y la
    captura de la hoja real la muestra con `0` en todas las filas. `DETRACCION` e `IMPORTACION` ya lo hacian."""
    compra = _filas(_compra())
    assert {f["DOCUMENTO ANULADO"] for f in compra} == {"0"}
    assert {f["IMPORTACION"] for f in compra} == {"0"}
    assert {f["IGV POR APLICAR"] for f in compra} == {"0"}
    assert {f["DETRACCION"] for f in compra} == {"0"}, "esta compra no lleva detraccion, y se dice"
    # En ventas la columna se llama `DOCUMENTO ANULADO`: son dos plantillas y cada una usa sus nombres.
    ventas = _filas(_venta(), imputacion={"fila-1": {"cuenta_contable": "70111000", "centro_costo": "CC01"}})
    assert {f["DOCUMENTO ANULADO"] for f in ventas} == {"0"}
    assert {f["EXPORTACION"] for f in ventas} == {"0"}


def test_el_numero_del_documento_va_pegado_y_con_ceros():
    """`F13600000431`: serie a cuatro y número a ocho, al revés que en CONCAR y el SIRE."""
    fila = _filas(_compra())[0]
    assert fila["NRO DOCUMENTO"] == "F13600000431"


def test_la_glosa_lleva_el_documento_y_la_de_movimiento_el_concepto():
    """Los treinta ejemplos oficiales lo traen asi: `FT 002-000085 /` arriba y el concepto al lado.

    Del 21 al 22-sep-2026 las dos dijeron el concepto, porque repetir el tipo y el numero —que ya viajan en sus
    propias columnas— parecia gastar la glosa en decir dos veces lo mismo. El manual dice otra cosa y manda el
    manual: entre lo que parece y lo que hace su sistema, gana lo segundo."""
    for fila in _filas(_compra()):
        assert fila["GLOSA"] == "FT F136-00000431 /"
        assert fila["GLOSA MOVIMIENTO"] == "CELULARES"
    ventas = _filas(_venta(), imputacion={"fila-1": {"cuenta_contable": "70111000", "centro_costo": "CC01"}})
    for fila in ventas:
        assert fila["GLOSA"] == "FT F001-00000123 /"
        assert fila["GLOSA MOVIMIENTO"] == "CELULARES"


def test_la_nota_de_credito_se_llama_CC_y_no_NC():
    """La divergencia más peligrosa con CONCAR, porque `FT` y `BV` sí coinciden.

    Heredar la tabla del asiento sin tocarla dejaría salir un archivo con `NC` dentro: STARSOFT lo importaría y
    clasificaría la nota de crédito como otra cosa. No da error; da contabilidad equivocada.
    """
    doc = _compra(tipo_cp="07", ref_tipo_cp="01", ref_serie="F136", ref_numero="431", ref_fecha="2025-07-01")
    assert _filas(doc)[0]["TIPO DOCUMENTO"] == "CC"

    de_concar = api.configuracion_por_defecto()["concar"]["tipos"]["07"]["sigla"]
    assert de_concar == "NC", "si CONCAR cambiara, este test deja de comparar lo que cree"


def test_un_tipo_de_comprobante_sin_sigla_detiene_la_exportacion():
    """La regla que el repositorio no negocia: una sigla que no se sabe no se inventa, se para.

    De las ocho de la tabla solo constan tres; las otras cinco son un punto de partida heredado de CONCAR y
    marcado como tal. Pero un tipo que NO está en la tabla —el `31`, transporte de bienes— no tiene de dónde
    salir, y ahí el driver se niega en vez de escribir algo plausible.
    """
    doc = _compra(tipo_cp="31")
    with pytest.raises(api.SinSigla):
        api.exportar(doc, driver="starsoft", configuracion=CONFIG,
                     imputacion={"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})

    con_sigla = {**CONFIG, "starsoft": {**CONFIG["starsoft"], "tipos": {"31": {"sigla": "GRT"}}}}
    assert _filas(doc, config=con_sigla)[0]["TIPO DOCUMENTO"] == "GRT"


def test_las_cinco_siglas_que_no_constan_se_heredan_marcadas():
    """Documenta la única decisión de este driver que no se puede afirmar, para que se vea y se pueda revocar.

    `01`, `03` y `07` salen de los vídeos. Las otras cinco son las de CONCAR, puestas como defecto configurable
    porque sin ellas el golden de compras —que lleva un recibo de servicios públicos— no se exportaría, y un
    driver que se planta ante el comprobante más común no sirve para probar nada.
    """
    from contaperu.drivers.starsoft import datos

    constan = {"01": "FT", "03": "BV", "07": "CC"}
    heredadas = {"02": "RH", "05": "BA", "08": "ND", "12": "TK", "14": "RC"}
    assert {k: v["sigla"] for k, v in datos.TIPOS.items()} == {**constan, **heredadas}

    de_concar = api.configuracion_por_defecto()["concar"]["tipos"]
    for codigo, sigla in heredadas.items():
        assert de_concar[codigo]["sigla"] == sigla, f"{codigo} ya no es la de CONCAR: revisar de dónde sale"
    assert de_concar["07"]["sigla"] != constan["07"], "la nota de crédito es la divergencia que sí consta"


def test_el_igv_va_solo_en_la_linea_del_total():
    """Como en la captura: las otras dos filas del asiento lo llevan vacío.

    En compras la del total es la SEGUNDA desde la 2.5 —el orden del manual es IGV, proveedor, gasto—, y la tasa
    va con dos decimales, como la escriben sus ejemplos."""
    filas = _filas(_compra())
    assert [f["IGV"] for f in filas] == ["", "167.31", ""]
    assert [f["TASA IGV"] for f in filas] == ["", "18.00", ""]


@pytest.mark.parametrize("cambios,esperado", [
    ({"destino_igv": "DG"}, "001"),
    ({"destino_igv": "DGNG"}, "002"),
    ({"destino_igv": "DNG"}, "003"),
    ({"base_gravada": "0", "igv": "0", "exonerado": "1096.80", "total": "1096.80"}, "004"),
    ({"anio_dua": "2025", "cod_dep_aduanera": "118"}, "005"),
])
def test_el_destino_de_la_adquisicion_sale_del_comprobante(cambios, esperado):
    """La columna que CONCAR no tiene, y la razón de que la cabecera del asiento creciera en la 1.4.0.

    Los tres primeros son `destino_igv` traducido; el 004 y el 005 se deducen, porque STARSOFT mete en una sola
    columna dos preguntas: a qué se destina el IGV, y qué clase de operación es.
    """
    assert {f["DESTINO"] for f in _filas(_compra(**cambios))} == {esperado}


def test_una_compra_exonerada_no_sale_como_gravada():
    """El caso que obliga a no traducir `DG` a `001` a secas: el modelo pone `DG` por defecto a TODO comprobante,
    también a uno que no tiene IGV que destinar."""
    doc = _compra(base_gravada="0", igv="0", exonerado="1096.80", total="1096.80")
    assert doc["comprobantes"][0].get("destino_igv") is None      # nadie lo declaró
    assert {f["DESTINO"] for f in _filas(doc)} == {"004"}


def test_una_venta_lleva_el_cliente_donde_una_compra_lleva_el_proveedor():
    """Los dos libros NO comparten juego de columnas."""
    filas = _filas(_venta(), config={"usa_centros_costo": False},
                   imputacion={"fila-1": {"cuenta_contable": "70410100"}})
    assert filas[0]["RUC CLIENTE"] == PROVEEDOR and filas[0]["RAZON SOCIAL"] == "CLIENTE DE PRUEBA SAC"
    assert "DESTINO" not in filas[0], "el destino del crédito fiscal es de una compra, no de una venta"


def test_una_glosa_larga_no_cabe_y_se_dice_antes_de_exportar():
    """El único límite que consta: está escrito en la cabecera de la hoja `PARAMETROS` («Máximo 60 caracteres»).

    Lo que vale no es que falle al exportar, sino que `diagnosticar` lo diga ANTES.
    """
    doc = _compra(concepto="C" * 61)
    diagnostico = api.diagnosticar(doc, driver="starsoft", configuracion=CONFIG,
                                   imputacion={"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})
    assert diagnostico["listo_para_exportar"] is False
    assert any("60 caracteres" in motivo for motivo in diagnostico["faltantes"]["no_cabe"])

    with pytest.raises(api.NoCabe):
        api.exportar(doc, driver="starsoft", configuracion=CONFIG,
                     imputacion={"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})


def test_el_archivo_se_llama_como_los_demas_sistemas():
    """`SISTEMA_LIBRO_PERIODO_RUC`, la regla de `kit.nombre_de_archivo` (2.1). El ZIP comparte su nombre base."""
    r = _exportar(_compra())
    assert r["archivo"] == f"STARSOFT_COMPRAS_202507_{RUC}.txt"
    assert r["archivo_zip"] == f"STARSOFT_COMPRAS_202507_{RUC}.zip"
    assert r["resumen"]["debe"] == r["resumen"]["haber"] == "1096.80"


def test_el_txt_viaja_dentro_de_un_zip_de_un_solo_miembro():
    """Lo que se descarga es el ZIP, y dentro va el TXT con su nombre. Como el del SIRE."""
    r = _exportar(_compra())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(r["zip_base64"]))) as z:
        assert z.namelist() == [r["archivo"]]


def test_el_mismo_contenido_da_el_mismo_zip_byte_a_byte():
    """La fecha de la entrada es fija, así que el ZIP es reproducible y quien guarde su huella lo reconoce.

    Estaba afirmado en el docstring del pipeline desde que existe el SIRE, y no lo probaba nadie."""
    uno, otro = _exportar(_compra()), _exportar(_compra())
    assert uno["zip_base64"] == otro["zip_base64"]


def test_el_txt_no_lleva_cabecera_y_su_primera_linea_ya_es_un_asiento():
    """Ningún TXT de STARSOFT de los vistos la lleva, y una cabecera se importaría como un asiento más."""
    primera = _texto(_exportar(_compra())).split("\r\n")[0]
    assert primera.startswith("40111000|202507|04|0001|")   # el IGV abre el asiento (2.5)
    assert "CTA CONTABLE" not in _texto(_exportar(_compra()))


def test_ninguna_fecha_sale_en_iso():
    """STARSOFT las quiere `DD/MM/AAAA` y el estándar las trae en ISO; hasta la 2.2 salían sin traducir.

    Se comprueba sobre TODAS las columnas declaradas `fecha` de los dos libros, y no sobre una lista escrita a
    mano: así el día que se añada una columna de fecha, este test ya la cubre."""
    for documento, imputacion in ((_compra(), None),
                                  (_venta(), {"fila-1": {"cuenta_contable": "70111000", "centro_costo": "CC01"}})):
        tipo = documento["libro"]["tipo"]
        fechas = [cab for _, cab, clase in starsoft.COLUMNAS[tipo] if clase == "fecha"]
        assert fechas, tipo
        for fila in _filas(documento, imputacion=imputacion):
            for columna in fechas:
                valor = fila[columna]
                assert not valor or re.fullmatch(r"\d{2}/\d{2}/\d{4}", valor), f"{tipo} · {columna} = {valor!r}"


def test_un_palote_en_la_razon_social_no_parte_la_linea():
    """El separador dentro de un campo correría todos los siguientes, y en un formato por posición eso es
    contabilidad en la columna de al lado."""
    documento = _venta()
    documento["comprobantes"][0]["contraparte_nombre"] = "ACME | SAC"
    filas = _filas(documento, imputacion={"fila-1": {"cuenta_contable": "70111000"}})
    assert filas[0]["RAZON SOCIAL"] == "ACME SAC"


def test_el_tipo_de_cambio_sale_tambien_en_soles_cuando_el_comprobante_lo_trae():
    """Su hoja lo lleva en todas las filas, también en operaciones en PEN (John, 21-sep-2026).

    El motor no lo inventa: lo transporta si llega. Quien lo pondrá es la aplicación que integra."""
    assert {f["TIPO CAMBIO"] for f in _filas(_compra(tipo_cambio="3.274"))} == {"3.274"}
    assert {f["TIPO CAMBIO"] for f in _filas(_compra())} == {""}


def test_el_resumen_trae_los_rangos_del_sub_diario_y_no_una_lista():
    """Lo que un ERP guarda para proponer el correlativo del mes siguiente.

    Hasta la 2.0 este driver devolvía `["04"]` y PISABA el diccionario de rangos del núcleo
    (`pipeline/armado.py` funde el extra del driver encima): quien lo leyera esperando un dict —como hace
    contab-core al recordar los correlativos— se encontraba una lista."""
    r = api.exportar(_compra(), driver="starsoft", configuracion=CONFIG,
                     imputacion={"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})
    rango = r["resumen"]["sub_diarios"]["04"]
    assert {"desde", "hasta", "comprobantes", "desde_codigo", "hasta_codigo", "desborda"} <= set(rango)
    assert (rango["desde"], rango["hasta"], rango["desde_codigo"]) == (1, 1, "070001")


def test_una_compra_con_detraccion_lleva_sus_datos_en_las_columnas():
    """Los tres datos de la detracción, cada uno el que es. Los dos primeros se mapearon mal al escribirlo.

    El CODIGO es el de SUNAT (`027`, Catalogo 54), no el interno que CONCAR mapea en su tabla (`02702`): son
    tablas de cada sistema y no consta que STARSOFT use una. El IMPORTE es lo DETRAIDO —«cuánto ha sido el
    importe que se ha detraído» (compras 10:58)— y no la base sobre la que se calcula, que es el total.
    """
    doc = _compra(base_gravada="1000.00", igv="180.00", total="1180.00", concepto="TRANSPORTE",
                  detraccion={"codigo": "027", "porcentaje": 4, "monto": "47.20"})
    filas = _filas(doc, config={"usa_centros_costo": False},
                   imputacion={"fila-1": {"cuenta_contable": "63110000"}})
    con_detraccion = [f for f in filas if f["CODIGO DETRACCION"]]
    assert len(con_detraccion) == 1
    assert con_detraccion[0]["CODIGO DETRACCION"] == "027", "el de SUNAT, no el interno de CONCAR"
    assert con_detraccion[0]["TASA DETRACCION"] == "4.00"
    assert con_detraccion[0]["IMPORTE DETRACCION"] == "47.00", "lo detraído, no la base"


def test_una_compra_con_detraccion_no_se_va_a_un_sub_diario_que_starsoft_no_tiene():
    """En CONCAR las compras con detracción tienen su propio registro (el `10`); en STARSOFT no consta que exista.

    Con `sub_diario_detraccion` vacío el motor las manda al de compras, que es lo que hace cualquier sistema que
    no los separa. Antes de esto salían al `10`, heredado de CONCAR, que es un sub-diario de otro sistema.
    """
    doc = _compra(detraccion={"codigo": "027", "porcentaje": 4, "monto": "47.20"})
    filas = _filas(doc, config={"usa_centros_costo": False},
                   imputacion={"fila-1": {"cuenta_contable": "63110000"}})
    assert {f["SUBDIARIO"] for f in filas} == {"04"}


# ── Contra el manual oficial (22-sep-2026) ───────────────────────────────────────────────
#
# Hasta hoy este driver se calcó de CAPTURAS de la hoja PLANTILLA de Excel. John consiguió la
# documentación de STARSOFT —`CONT_COMPRAS` y `CONT_VENTAS`, con la tabla de campos y ejemplos de TXT
# sacados del propio sistema— y esos ejemplos desmintieron tres cosas. Lo que sigue las fija.
#
# La regla que lo explica todo, y que la plantilla de Excel escondía: **el número del ítem en el manual
# NO es su posición en la línea**. Las columnas que dependen de un «concepto general» de cada
# instalación no se escriben, y por tanto no ocupan sitio. Escribiéndolas, la línea salía con tres
# campos de más en compras y siete de más en ventas.

def test_la_linea_tiene_los_campos_del_ejemplo_oficial():
    """35 en compras y 27 en ventas, contados en los ejemplos del manual.

    Antes salían 38 y 34: se escribían las condicionales (compras `NRO FILE`, `OTROS TRIBUTOS` e
    `IMP BOLSA`; ventas esas y además `NUM DOC FINAL`, `VALOR ISC`, `OTROS TRIB` y `EXONERADO`), y el
    manual dice literal: «si el concepto está en falso, no incluir la columna».
    """
    assert len(_texto(_exportar(_compra())).split("\r\n")[0].split("|")) == 35
    assert len(_texto(_exportar(_venta())).split("\r\n")[0].split("|")) == 27


def test_la_fecha_del_documento_es_la_emision_y_la_de_registro_la_del_periodo():
    """Las dos reglas del manual, que solo se ven cuando el comprobante es EXTEMPORÁNEO.

    Campo 5 de compras (`FECHA DEL DOCUMENTO`): «menor o igual al campo 15 (fecha de Registro) y debe
    corresponder al periodo». Campo 15 (`FECHA DE REGISTRO`): «debe corresponder al periodo informado».
    Hasta la 2.3 se escribían al revés —la del asiento en la del documento y la emisión en la de
    registro—, así que una factura de julio anotada en agosto rompía las dos a la vez: el 5 salía
    mayor que el 15 y el 15 no era del periodo. Con el comprobante dentro de su mes no se notaba.
    """
    doc = _compra(fecha_emision="2025-06-20", fecha_vencimiento="2025-07-20")   # junio, anotado en julio
    fila = _filas(doc)[0]
    assert fila["FECHA DOCUMENTO"] == "20/06/2025", "la del documento es la EMISIÓN"
    assert fila["FECHA REGISTRO"] == "01/07/2025", "la de registro cae dentro del periodo 202507"

    # En ventas el manual las coloca al revés: el campo 5 es la de registro y la emisión es el 11.
    venta = _filas(_venta(fecha_emision="2025-06-20", fecha_vencimiento="2025-07-20"))[0]
    assert venta["FECHA REGISTRO"] == "01/07/2025" and venta["FECHA EMISION"] == "20/06/2025"


def test_el_tipo_de_conversion_va_en_TODAS_las_lineas():
    """Y no solo en la del tercero, aunque lo parezca.

    Es la observación que John retiró: los ejemplos oficiales traen `VTA` en las tres líneas —la del
    gasto, la del IGV y la del proveedor— y el manual de compras lo da por obligatorio sin distinguir
    por cuenta. En ventas añade «en las demás cuentas puede estar en blanco», o sea que rellenarlo
    también vale. Sin este test, la duda volvería.
    """
    for filas in (_filas(_compra()), _filas(_venta())):
        assert [f["CONV"] for f in filas] == ["VTA"] * len(filas)
