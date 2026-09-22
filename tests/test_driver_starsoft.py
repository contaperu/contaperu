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
    """El asiento tipo 1 de STARSOFT: gasto al debe, IGV al debe, pasivo al haber."""
    filas = _filas(_compra())
    assert [(f["CTA CONTABLE"], f["DEBE / HABER"], f["IMPORTE"]) for f in filas] == [
        ("60111000", "D", "929.49"), ("401111", "D", "167.31"), ("421201", "H", "1096.80")]


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


def test_las_dos_glosas_dicen_lo_mismo_y_es_el_concepto():
    """`GLOSA` y `GLOSA MOVIMIENTO` llevan las dos el concepto del comprobante (John, 21-sep-2026).

    Hasta la 2.1 la primera llevaba el documento (`FT F136-00000431 /`), pero el tipo y el número ya viajan en
    sus propias columnas: repetirlos gastaba la glosa en decir dos veces lo mismo."""
    for fila in _filas(_compra()):
        assert fila["GLOSA"] == fila["GLOSA MOVIMIENTO"] == "CELULARES"
    ventas = _filas(_venta(), imputacion={"fila-1": {"cuenta_contable": "70111000", "centro_costo": "CC01"}})
    for fila in ventas:
        assert fila["GLOSA"] == fila["GLOSA MOVIMIENTO"] == "CELULARES"


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
    """Como en la captura: las otras dos filas del asiento lo llevan vacío."""
    filas = _filas(_compra())
    assert [f["IGV"] for f in filas] == ["", "", "167.31"]
    assert [f["TASA IGV"] for f in filas] == ["", "", "18"]


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
    assert primera.startswith("60111000|202507|04|0001|")
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
    assert con_detraccion[0]["TASA DETRACCION"] == "4"
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
