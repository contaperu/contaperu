"""Las dos retenciones de una compra, cada una con su nombre (4.0, enmiendas 0005 y el renombrado).

Hasta la 3.3 el comprobante tenía **un** campo llamado `retencion`, y el Perú tiene dos retenciones
que se escriben igual en castellano: la **renta de 4ta** del 8 % de un recibo por honorarios y el
**Régimen de Retenciones del IGV** del 3 % de una factura. Ese nombre genérico costó dos averías
reales, y las dos están escritas en el repositorio:

1. Un `retencion_4ta` donde el campo se llamaba `retencion` **exportaba el mes entero sin su línea
   de retención**, y solo se veía leyendo las celdas del Excel (`de_dict`, y el caso que lo fija en
   `test_serializacion.py`). El lector se lo tragaba en silencio.
2. Una aplicación que integra el motor volcó en ese campo el 3 % del IGV que SUNAT declara de una
   factura, porque **no había dónde ponerlo**: dos facturas de producción acabaron observadas con
   `RETENCION_NO_APLICA` (20-oct-2026). El aviso del motor era lo único que estaba bien.

La segunda es el **caso real** que la enmienda 0005 esperaba desde que reservó el nombre
`retencion_igv`: «un destino que lo pida». Este archivo es esa enmienda hecha pruebas, y además
fija lo que el renombrado **no** debe mover — que es la mitad que importa de una versión mayor.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from contaperu import api, asiento
from contaperu.modelo import Comprobante, Libro
from contaperu.tributos import validar

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
         "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-08-11",
           "contraparte_tipo_doc": "6", "contraparte_doc": "20602222226",
           "contraparte_nombre": "PROVEEDOR SAC", "moneda": "PEN",
           "base_gravada": "630.00", "igv": "113.40", "total": "743.40", "concepto": "DIESEL"}
HONORARIOS = {"tipo_cp": "02", "serie": "E001", "numero": "45", "fecha_emision": "2026-08-11",
              "contraparte_tipo_doc": "6", "contraparte_doc": "20607777773",
              "contraparte_nombre": "PROFESIONAL", "moneda": "PEN",
              "inafecto": "2000.00", "total": "2000.00", "concepto": "ASESORIA"}
# El 3,00 % exacto de 743.40, que son los números de la factura que destrabó esto.
DEL_IGV = {"porcentaje": "3.00", "monto": "22.30"}


def documento(base=None, **extra) -> dict:
    return {"open_accounting": "4.0", "libro": dict(LIBRO),
            "comprobantes": [dict(base or FACTURA, **extra)]}


def _revisado(base=None, **extra) -> Comprobante:
    c = Comprobante(**dict(base or FACTURA, **extra))
    validar.validar(c, Libro(**LIBRO))
    return c


def _codigos(c: Comprobante) -> list[str]:
    return [o.codigo for o in c.observaciones]


# --- el estándar: qué admite y qué no ---------------------------------------------------------

def test_el_estandar_admite_el_bloque_de_la_retencion_del_igv():
    assert api.verificar_documento(documento(retencion_igv=DEL_IGV))["conforme"] is True


# El PORCENTAJE no lleva patrón, igual que el de la detracción (`anyOf` de texto o número): la forma
# fina del dato es de quien lo escribe y el motor avisa de la tasa en `validar`, que es donde hay
# contexto para decidir. Lo que el esquema sí cierra es el BLOQUE y el importe.
@pytest.mark.parametrize("bloque", [
    {"porcentaje": "3.00", "monto": "22.30", "tributo": "1000"},   # una clave de más: bloque cerrado
    {"porcentaje": "3.00", "monto": "22,30"},                      # la coma no es un importe
])
def test_el_estandar_rechaza_un_bloque_que_no_tiene_esa_forma(bloque: dict):
    assert api.verificar_documento(documento(retencion_igv=bloque))["conforme"] is False


def test_ausente_y_nulo_son_lo_mismo_y_los_dos_valen():
    """«Nadie lo dijo» no es «se dijo que no hay», y por eso el campo no tiene un cero de fábrica."""
    assert api.verificar_documento(documento())["conforme"] is True
    assert api.verificar_documento(documento(retencion_igv=None))["conforme"] is True
    assert Comprobante(**FACTURA).retencion_igv is None


def test_las_dos_conviven_en_el_mismo_comprobante():
    """No son excluyentes por el esquema —lo son por el tipo de comprobante, que es otra cosa—, y
    el documento tiene que poder decir las dos."""
    c = Comprobante(**dict(HONORARIOS, retencion_4ta="160.00", retencion_igv=DEL_IGV))
    assert c.retencion_4ta == Decimal("160.00") and c.retencion_igv == DEL_IGV


# --- el renombrado: la clave vieja dice cuál de las dos quieres ---------------------------------

def test_la_clave_vieja_no_se_traga_en_silencio_y_nombra_las_dos():
    """Es la lección de la avería 1, aplicada al propio renombrado: quien manda `retencion` no se
    equivocó de sitio, se equivocó de época, y lo que necesita leer es cuál de las dos quiere."""
    with pytest.raises(ValueError, match="retencion_4ta.*retencion_igv"):
        Comprobante.de_dict({**FACTURA, "retencion": "22.30"})


def test_el_documento_con_la_clave_vieja_se_rechaza_entero():
    """Y por la puerta del documento también: un integrador que no haya migrado lo sabe al primer
    intento, no cuando le falte una línea en el Excel."""
    assert api.verificar_documento(documento(retencion="22.30"))["conforme"] is False


# --- el catálogo: lo que avisa -----------------------------------------------------------------

def test_la_retencion_del_igv_al_3_por_ciento_no_dice_nada():
    assert _codigos(_revisado(retencion_igv=DEL_IGV)) == []


def test_un_porcentaje_que_no_es_el_del_regimen_avisa():
    """Aviso y nunca error: no entra en ningún asiento, así que no puede frenarle el mes a nadie —la
    misma regla que `medio_pago`—. Y avisa sin mirar la fecha, como la tasa del IGV."""
    c = _revisado(retencion_igv={"porcentaje": "6.00", "monto": "44.60"})
    observacion = next(o for o in c.observaciones if o.codigo == "RETENCION_IGV_TASA")
    assert observacion.nivel == "aviso"
    assert "6.00" in observacion.texto and "3 %" in observacion.texto
    assert c.retencion_igv == {"porcentaje": "6.00", "monto": "44.60"}, "el valor se respeta"
    assert not c.tiene_errores


def test_el_aviso_de_la_tasa_no_bloquea_la_exportacion():
    d = api.diagnosticar(documento(retencion_igv={"porcentaje": "6.00", "monto": "44.60"}),
                         driver="sire")
    assert d["listo_para_exportar"] is True


def test_la_del_igv_en_una_factura_NO_dispara_el_aviso_de_la_de_4ta():
    """El corazón del asunto, dicho como prueba: hasta la 3.3 este dato acababa en el campo de la
    4ta y el motor decía «la retención de 4ta solo se registra en recibos por honorarios». Con su
    propio campo, la misma factura no tiene ni una observación."""
    assert "RETENCION_NO_APLICA" not in _codigos(_revisado(retencion_igv=DEL_IGV))


def test_la_de_4ta_en_una_factura_SIGUE_avisando_y_ahora_dice_adonde_va():
    """El aviso que delató la avería no se toca: si alguien vuelve a poner un importe de 4ta en una
    factura, sigue sonando. Lo que gana es la salida: nombrar el campo que sí existe."""
    c = _revisado(retencion_4ta="22.30")
    observacion = next(o for o in c.observaciones if o.codigo == "RETENCION_NO_APLICA")
    assert observacion.nivel == "aviso"
    assert "retencion_igv" in observacion.texto


def test_la_de_4ta_conserva_sus_tres_reglas():
    """El renombrado no es una reescritura: las tres observaciones de la de 4ta siguen donde
    estaban, con sus mismos códigos y niveles."""
    assert _codigos(_revisado(HONORARIOS, retencion_4ta="160.00")) == []
    mayor = _revisado(HONORARIOS, retencion_4ta="2500.00")
    assert "RETENCION_MAYOR" in _codigos(mayor) and mayor.tiene_errores
    assert "RETENCION_TASA" in _codigos(_revisado(HONORARIOS, retencion_4ta="300.00"))


# --- el asiento: la del IGV no mueve ni una línea -----------------------------------------------

def _asiento_de(**extra) -> list[dict]:
    """El asiento NEUTRAL, que es el que dice si un campo entra en la contabilidad: los legacy
    pueden omitir columnas por su formato y taparían la diferencia."""
    doc = documento(**extra)
    doc["comprobantes"][0]["id_externo"] = "f1"
    return api.generar_asiento(doc, driver="asiento_contable",
                               imputacion={"f1": {"cuenta_contable": "631101"}})["asiento"]


def test_una_factura_con_retencion_del_igv_da_EL_MISMO_asiento_que_sin_ella():
    """El criterio de salida de la enmienda 0005, y la razón por la que este campo es seguro: **no
    es un hecho del comprobante sino del pago**, así que no toca compras, ni ventas, ni el neutral.
    Si esta prueba cae, el campo dejó de ser de transporte y se convirtió en contabilidad."""
    assert _asiento_de(retencion_igv=DEL_IGV) == _asiento_de()


def test_un_recibo_con_retencion_de_4ta_SI_parte_su_asiento():
    """Y la otra mitad: la de 4ta sigue haciendo lo que hacía. El gasto va por el total, la
    retención al haber en su cuenta de tributos y al profesional se le debe solo el neto."""
    doc = documento(HONORARIOS, retencion_4ta="160.00")
    doc["comprobantes"][0]["id_externo"] = "h1"
    lineas = api.generar_asiento(doc, driver="asiento_contable",
                                 imputacion={"h1": {"cuenta_contable": "631101"}})["asiento"]
    de_la_retencion = [ln for ln in lineas if ln.get("retencion")]
    assert len(de_la_retencion) == 1, lineas
    assert de_la_retencion[0]["importe"] == "160.00"
    # Y al profesional se le debe el NETO, que es lo que esa línea parte.
    assert any(ln["importe"] == "1840.00" for ln in lineas), lineas


# --- el hecho llega al driver -------------------------------------------------------------------

def test_la_retencion_del_igv_llega_a_la_cabecera_del_asiento():
    """La regla de `test_cabecera.py`: todo hecho del comprobante llega al driver, o el próximo
    descubre —como STARSOFT— que el dato existe en el estándar y se cae por el camino.

    **No entrar en un asiento y no llegar al driver no son lo mismo**, y la diferencia es justo lo
    que este caso fija: ningún driver lo usa hoy, y CONTASIS lo pedirá en su «condición de
    retención».
    """
    cabecera = asiento.cabecera_de(Comprobante(**dict(FACTURA, retencion_igv=DEL_IGV)))
    assert cabecera.retencion_igv == {"porcentaje": "3.00", "monto": "22.30"}
    assert cabecera.retencion_4ta == "0.00"


def test_sin_retencion_el_bloque_se_OMITE_del_documento_en_vez_de_salir_vacio():
    """Porque el estándar distingue «no lo sé» de «es esto», y lo primero se dice omitiendo la
    clave. Un `{}` en el documento diría que se comprobó y no hay."""
    assert "retencion_igv" not in asiento.cabecera_de(Comprobante(**FACTURA)).como_comprobante()


# --- el lector de XML: un término de pago, dos destinos -----------------------------------------

def _xml_con_retencion(ruta: str) -> bytes:
    """El XML real de la batería, con el término de pago de la retención insertado.

    La FORMA del bloque no se inventa aquí: es la que `xml_ubl` ya lee desde antes de esta versión
    (`cac:PaymentTerms` con `cbc:ID = "Retencion"`, su `PaymentPercent` y su `Amount`). Lo que esta
    versión cambia no es cómo se lee, sino **dónde aterriza**. El día que haya un XML real de un
    agente de retención, entra como fixture y este ayudante se retira.

    **Ese día no es el 24-oct-2026**, aunque lo parezca: ese día entró un recibo por honorarios real
    (`10601111115-02-E001-186.xml`), y su retención es la de **4ta**, que llega por `cac:TaxTotal` y
    no por el término de pago. El 3 % del Régimen de Retenciones del **IGV** sigue sin archivo real,
    así que este ayudante se queda.

    Se usa el **124** y no el 123 porque aquél llega con detracción, y una factura con detracción y
    retención a la vez no es un caso real: si hay SPOT no hay retención. El 124 trae solo su forma de
    pago, y además viene en USD —que prueba de paso que el bloque viaja como lo dice el papel—.
    """
    from pathlib import Path
    crudo = (Path(__file__).parent / "fixtures" / "xml" / ruta).read_bytes().decode("utf-8")
    bloque = ("<cac:PaymentTerms><cbc:ID>Retencion</cbc:ID>"
              "<cbc:PaymentPercent>3.00</cbc:PaymentPercent>"
              '<cbc:Amount currencyID="PEN">22.30</cbc:Amount></cac:PaymentTerms>')
    assert "Retencion" not in crudo, "este XML ya trae la retención: el caso no probaría nada"
    marca = "<cac:TaxTotal>"
    assert marca in crudo
    return crudo.replace(marca, bloque + marca, 1).encode("utf-8")


def test_en_una_FACTURA_el_termino_de_pago_es_la_retencion_del_igv():
    """Hasta la 3.3 este dato se leía y **se tiraba**: llegaba hasta el constructor y se cambiaba
    por un cero. Existía en el XML, sobrevivía en `datos_originales` y no había campo donde
    ponerlo. Esa es la ausencia que la enmienda 0005 cerró."""
    libro = Libro(ruc="20604444447", razon_social="CLIENTE DE PRUEBA S.A.", periodo="202601",
                  tipo="compra")
    doc = api.leer_xml(_xml_con_retencion("20131312955-01-F001-124.xml").decode("utf-8"),
                       dict(ruc=libro.ruc, razon_social=libro.razon_social,
                            periodo=libro.periodo, tipo="compra"))
    c = Comprobante.de_dict(doc["comprobantes"][0])
    assert c.retencion_igv == {"porcentaje": "3.00", "monto": "22.30"}
    assert c.retencion_4ta == Decimal("0.00"), "en una factura no hay renta de 4ta"
    assert c.datos_originales["retencion"] == c.retencion_igv, "y el crudo sigue en el rastro"


# --- y la otra mitad: el RECIBO, cuya retención no viene del término de pago -------------------
# Entró el 24-oct-2026 con el primer recibo por honorarios real de la batería. Hasta entonces este
# archivo solo tenía la mitad del IGV, y la de 4ta se probaba con comprobantes dictados a mano.

RECIBO = "10601111115-02-E001-186.xml"
COMPRAS_RECIBO = dict(ruc="20604444447", razon_social="CLIENTE DE PRUEBA S.A.",
                      periodo="202601", tipo="compra")


def _recibo() -> dict:
    from pathlib import Path
    crudo = (Path(__file__).parent / "fixtures" / "xml" / RECIBO).read_text(encoding="utf-8")
    return api.leer_xml(crudo, COMPRAS_RECIBO)


def test_en_un_RECIBO_la_retencion_sale_del_TaxTotal_y_no_del_termino_de_pago():
    """El espejo del caso de la factura, y la diferencia está en de dónde sale el dato: el recibo
    real **no trae** `PaymentTerms Retencion` —su único término de pago es `FormaPago`—, así que la
    4ta se lee de `cac:TaxTotal`. Por eso no basta con mirar el término de pago para las dos."""
    c = Comprobante.de_dict(_recibo()["comprobantes"][0])
    assert c.tipo_cp == "02"
    assert c.retencion_4ta == Decimal("196.00")
    assert c.retencion_igv is None, "en un recibo no hay retención del IGV"
    assert c.datos_originales["retencion"] is None, "y el término de pago no trae nada"
    assert c.datos_originales["honorarios"]["porcentaje"] == "8.00"


def test_el_asiento_del_recibo_leido_del_XML_cuadra_y_va_al_sub_diario_15():
    """El círculo cerrado: un recibo leído del XML aterriza en el MISMO asiento que uno dictado a
    mano —tres líneas, sub-diario 15, la cuenta de terceros 424101 y la retención en su cuenta—.
    Y cuadra, que es lo que demuestra que el bruto en `total` es la forma correcta: si el total
    fuera el neto, el gasto no cubriría las dos líneas del Haber."""
    doc = _recibo()
    doc["comprobantes"][0]["id_externo"] = "recibo-1"
    lineas = api.generar_asiento(
        doc, driver="concar",
        imputacion={"recibo-1": {"cuenta_contable": "631101", "centro_costo": "01"}},
        correlativos={"02": "080001"})["asiento"]
    assert [(l["cuenta"], l["debe_haber"], l["importe"]) for l in lineas] == [
        ("631101", "D", "2450.00"),      # el gasto, por el BRUTO
        ("401721", "H", "196.00"),       # la retención de 4ta
        ("424101", "H", "2254.00"),      # lo que se le debe al profesional
    ]
    assert {l["sub_diario"] for l in lineas} == {"15"}
    assert lineas[1]["retencion"] == {"codigo": "3000", "categoria": "4"}
    assert lineas[2]["contraparte_doc"] == "10601111115"
    debe = sum(Decimal(l["importe"]) for l in lineas if l["debe_haber"] == "D")
    haber = sum(Decimal(l["importe"]) for l in lineas if l["debe_haber"] == "H")
    assert debe == haber == Decimal("2450.00")
