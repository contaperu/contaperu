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
import csv
import io

import pytest

from contaperu import api

RUC = "20601234567"
PROVEEDOR = "20131312955"
CONFIG = {"usa_centros_costo": True, "starsoft": {"tipo_anexo": "03"}}


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


def _filas(documento, config=None, imputacion=None) -> list[dict]:
    """Las filas del archivo, ya parseadas, como las vería quien abre el CSV."""
    r = api.exportar(documento, driver="starsoft", configuracion=config or CONFIG,
                     imputacion=imputacion or {"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})
    texto = base64.b64decode(r["contenido_base64"]).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def test_una_compra_sale_con_las_tres_lineas_del_asiento_tipico():
    """El asiento tipo 1 de STARSOFT: gasto al debe, IGV al debe, pasivo al haber."""
    filas = _filas(_compra())
    assert [(f["CUENTA"], f["DEBE HABER"], f["IMPORTE"]) for f in filas] == [
        ("60111000", "D", "929.49"), ("401111", "D", "167.31"), ("421201", "H", "1096.80")]


def test_el_sub_diario_de_compras_es_el_de_starsoft_y_no_el_de_concar():
    """`4`, no `11`. «El subdiario por defecto para compras es cuatro según el sistema contable» (compras 6:08)."""
    assert {f["SUBDIARIO"] for f in _filas(_compra())} == {"4"}


def test_el_sub_diario_de_ventas_tambien():
    """`03`, no `05` (John, 20-sep-2026)."""
    filas = _filas(_venta(), config={"usa_centros_costo": False},
                   imputacion={"fila-1": {"cuenta_contable": "70410100"}})
    assert {f["SUBDIARIO"] for f in filas} == {"03"}


def test_el_voucher_va_limpio_y_no_con_el_mes_delante():
    """El motor numera `070001`; STARSOFT empieza en 1 y sigue (compras 6:15)."""
    assert {f["VOUCHER"] for f in _filas(_compra())} == {"1"}


def test_el_numero_del_documento_va_pegado_y_con_ceros():
    """`F13600000431`, al revés que en CONCAR y el SIRE, donde va sin ceros. Y la glosa, con guion."""
    fila = _filas(_compra())[0]
    assert fila["NRO DOCUMENTO"] == "F13600000431"
    assert fila["GLOSA"] == "FT F136-00000431"


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


def test_el_archivo_se_llama_por_su_ruc_periodo_y_libro():
    r = api.exportar(_compra(), driver="starsoft", configuracion=CONFIG,
                     imputacion={"fila-1": {"cuenta_contable": "60111000", "centro_costo": "CC01"}})
    assert r["archivo"] == f"STARSOFT_{RUC}_202507_COMPRAS.csv"
    assert r["resumen"]["debe"] == r["resumen"]["haber"] == "1096.80"
