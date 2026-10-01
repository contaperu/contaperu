"""Los catálogos de SUNAT viven en datos, con su fuente (1.1, primer paso del hito C1).

Moverlos del código a `datos/sunat/catalogos.json` no puede cambiar ni un código ni un nombre: los valores de la 1.0
quedan escritos aquí, tal como estaban en `catalogos.py`.
"""
from __future__ import annotations

from decimal import Decimal

from contaperu import _datos, api, catalogos

TIPOS_CP_DE_LA_1_0 = {
    "00": "Otros", "01": "Factura", "02": "Recibo por honorarios", "03": "Boleta de venta",
    "04": "Liquidación de compra", "05": "Boleto de transporte aéreo", "06": "Carta de porte aéreo",
    "07": "Nota de crédito", "08": "Nota de débito", "09": "Guía de remisión", "10": "Recibo por arrendamiento",
    "12": "Ticket de máquina registradora", "13": "Documento de bancos y financieras",
    "14": "Recibo de servicios públicos", "16": "Boleto de transporte público", "18": "Documento de AFP",
    "21": "Conocimiento de embarque", "22": "Comprobante por operaciones no habituales",
    "25": "Operadores de contratos de colaboración", "36": "Documento de peaje", "46": "Constancia de pago (SUNAT)",
    "50": "DUA importación definitiva", "52": "Despacho simplificado de importación", "87": "Nota de crédito especial",
    "88": "Nota de débito especial", "91": "Comprobante de no domiciliado", "97": "Nota de crédito de no domiciliado",
    "98": "Nota de débito de no domiciliado",
}
TIPOS_DOC_IDENTIDAD_DE_LA_1_0 = {"0": "Otros", "1": "DNI", "4": "Carné de extranjería", "6": "RUC", "7": "Pasaporte",
                                 "A": "Cédula diplomática"}
MONEDAS_DE_LA_1_0 = frozenset({"PEN", "USD", "EUR", "CNY", "GBP", "JPY", "CLP", "COP", "BRL", "MXN"})


def test_los_catalogos_son_los_de_la_1_0():
    """Los mismos códigos, los mismos nombres y el mismo orden en los tipos de comprobante."""
    assert list(catalogos.TIPOS_CP.items()) == list(TIPOS_CP_DE_LA_1_0.items())
    assert catalogos.TIPOS_DOC_IDENTIDAD == TIPOS_DOC_IDENTIDAD_DE_LA_1_0
    assert catalogos.MONEDAS == MONEDAS_DE_LA_1_0


def test_cada_catalogo_viene_de_datos_con_su_fuente():
    datos = _datos.leer_json("datos/sunat/catalogos.json")
    # Siete desde la 5.0, cuando `tributos` entró. Es una igualdad de conjuntos y no un conteo a propósito: una tabla
    # nueva pone esto rojo y hay que decidirla, que es el único punto del repositorio donde «entró un catálogo de
    # SUNAT» se declara.
    assert set(datos) == {"tipos_comprobante", "tipos_documento_identidad", "monedas", "medios_pago",
                          "motivos_nota_credito", "motivos_nota_debito", "tributos"}
    assert all(tabla["fuente"].strip() for tabla in datos.values())
    assert catalogos.TIPOS_CP == datos["tipos_comprobante"]["codigos"]
    assert catalogos.FUENTES == {nombre: tabla["fuente"] for nombre, tabla in datos.items()}
    assert api.catalogos_sunat()["fuentes"] == catalogos.FUENTES


# ── Los medios de pago (Anexo 3 de la RS 169-2015) ─────────────────────────────────────────────────────────────

# Los 22 códigos, escritos a mano y enteros. Existe por un error concreto: la primera lista que llegó tenía tres
# filas y decía que `005` era «tarjeta de crédito». En el anexo `005` es **tarjeta de débito** y la de crédito
# emitida en el país es `006`. Un código publicado no se puede cambiar de significado después
# (`estandar/enmiendas/LEEME.md`), así que el que los vigila es este test y no la buena memoria de nadie.
MEDIOS_DE_PAGO_DE_SUNAT = {
    "001": "Depósito en cuenta",
    "002": "Giro",
    "003": "Transferencia de fondos",
    "004": "Orden de pago",
    "005": "Tarjeta de débito",
    "006": "Tarjeta de crédito emitida en el país por una empresa del sistema financiero",
    "007": "Cheques con la cláusula de «no negociable», «intransferibles», «no a la orden» u otra equivalente, "
           "a que se refiere el inciso g) del artículo 5° de la Ley",
    "008": "Efectivo, por operaciones en las que no existe obligación de utilizar medio de pago",
    "009": "Efectivo, en los demás casos",
    "010": "Medios de pago usados en comercio exterior",
    "011": "Documentos emitidos por las EDPYMES y las cooperativas de ahorro y crédito no autorizadas a captar "
           "depósitos del público",
    "012": "Tarjeta de crédito emitida en el país o en el exterior por una empresa no perteneciente al sistema "
           "financiero, cuyo objeto principal sea la emisión y administración de tarjetas de crédito",
    "013": "Tarjetas de crédito emitidas en el exterior por empresas bancarias o financieras no domiciliadas",
    "101": "Transferencias - Comercio exterior",
    "102": "Cheques bancarios - Comercio exterior",
    "103": "Orden de pago simple - Comercio exterior",
    "104": "Orden de pago documentario - Comercio exterior",
    "105": "Remesa simple - Comercio exterior",
    "106": "Remesa documentaria - Comercio exterior",
    "107": "Carta de crédito simple - Comercio exterior",
    "108": "Carta de crédito documentario - Comercio exterior",
    "999": "Otros medios de pago",
}


def test_los_medios_de_pago_son_los_del_anexo():
    """Los 22 códigos, con su texto y en el orden del anexo."""
    assert list(catalogos.MEDIOS_PAGO.items()) == list(MEDIOS_DE_PAGO_DE_SUNAT.items())


def test_la_tarjeta_de_debito_es_la_005_y_la_de_credito_la_006():
    """El error que motivó el catálogo, con nombre propio: son dos códigos distintos y dos tarjetas distintas."""
    assert catalogos.MEDIOS_PAGO["005"] == "Tarjeta de débito"
    assert catalogos.MEDIOS_PAGO["006"].startswith("Tarjeta de crédito emitida en el país")
    assert "crédito" not in catalogos.MEDIOS_PAGO["005"]


def test_los_medios_de_pago_salen_por_la_fachada_con_su_fuente():
    """Un ERP los lee por la API o por el recurso del MCP, no copiándolos."""
    catalogos_sunat = api.catalogos_sunat()
    assert catalogos_sunat["medios_pago"] == catalogos.MEDIOS_PAGO
    fuente = catalogos_sunat["fuentes"]["medios_pago"]
    # La fuente dice la norma Y el asunto: un número de tabla suelto no identifica nada y puede cambiar.
    assert "RS 169-2015" in fuente and "medio de pago" in fuente.lower()


# ── Por qué se emitió una nota: los Catálogos 09 y 10 del Anexo N.° 8 ──────────────────────────────────────────

# Escritos a mano y enteros, por el mismo motivo que los medios de pago: son texto de una norma y nadie los
# recuerda bien. El 09 vigente es el del Anexo III de la RS 193-2020, que lo llevó de 9 códigos a 13; el 10 es el
# del Anexo V de la RS 318-2017, que lo republicó sin cambios.
MOTIVOS_DE_NOTA_DE_CREDITO = {
    "01": "Anulación de la operación",
    "02": "Anulación por error en el RUC",
    "03": "Corrección por error en la descripción",
    "04": "Descuento global",
    "05": "Descuento por ítem",
    "06": "Devolución total",
    "07": "Devolución por ítem",
    "08": "Bonificación",
    "09": "Disminución en el valor",
    "10": "Otros conceptos",
    "11": "Ajustes de operaciones de exportación",
    "12": "Ajustes afectos al IVAP",
    "13": "Corrección del monto neto pendiente de pago y/o la(s) fechas(s) de vencimiento del pago único o de las "
          "cuotas y/o los montos correspondientes a cada cuota, de ser el caso",
}
MOTIVOS_DE_NOTA_DE_DEBITO = {
    "01": "Intereses por mora",
    "02": "Aumento en el valor",
    "03": "Penalidades/otros conceptos",
}


def test_los_trece_motivos_de_nota_de_credito_son_los_del_catalogo_09():
    """Los 13 códigos, con su texto y en el orden del anexo."""
    assert list(catalogos.MOTIVOS_NOTA_CREDITO.items()) == list(MOTIVOS_DE_NOTA_DE_CREDITO.items())


def test_los_tres_motivos_de_nota_de_debito_son_los_del_catalogo_10():
    """Tres y no más: al 10 no le añadieron los ajustes de exportación e IVAP que sí ganó el 09 en 2020."""
    assert list(catalogos.MOTIVOS_NOTA_DEBITO.items()) == list(MOTIVOS_DE_NOTA_DE_DEBITO.items())


def test_el_01_significa_cosas_distintas_en_los_dos_catalogos():
    """La razón de que sean DOS tablas y no una. Juntarlas obligaría a inventar un prefijo, y un catálogo con
    códigos inventados deja de ser el de SUNAT."""
    assert catalogos.MOTIVOS_NOTA_CREDITO["01"] == "Anulación de la operación"
    assert catalogos.MOTIVOS_NOTA_DEBITO["01"] == "Intereses por mora"
    assert catalogos.MOTIVOS_NOTA_CREDITO["01"] != catalogos.MOTIVOS_NOTA_DEBITO["01"]


def test_el_catalogo_de_una_nota_lo_elige_su_tipo_de_comprobante():
    """**El test que cierra el 87 para este campo.** Mirar solo `("07", "08")` —que es lo que dice
    `catalogos.TIPOS_NOTA`, y significa otra cosa— dejaría a la nota de crédito de no domiciliado y a la de débito
    especial sin catálogo EN SILENCIO: su código se avisaría como desconocido siempre."""
    assert catalogos.motivos_de_nota("07") is catalogos.MOTIVOS_NOTA_CREDITO
    assert catalogos.motivos_de_nota("87") is catalogos.MOTIVOS_NOTA_CREDITO
    assert catalogos.motivos_de_nota("08") is catalogos.MOTIVOS_NOTA_DEBITO
    assert catalogos.motivos_de_nota("88") is catalogos.MOTIVOS_NOTA_DEBITO
    # Lo que no es una nota no tiene motivo, y eso incluye el vacío y la basura.
    assert catalogos.motivos_de_nota("01") == {}
    assert catalogos.motivos_de_nota("") == {}
    assert catalogos.motivos_de_nota(None) == {}


def test_las_dos_listas_de_notas_dicen_lo_mismo():
    """`catalogos` y `modelo` son dos módulos hoja que no se importan entre sí, así que cada uno tiene su copia de
    los cuatro códigos de nota. Lo que impide que se separen es este test. Y `catalogos.NOTAS` se DERIVA de los dos
    conjuntos, así que dentro de `catalogos` no puede haber desacuerdo."""
    from contaperu import modelo
    assert set(catalogos.NOTAS_CREDITO) == set(modelo.NOTAS_CREDITO)
    assert set(catalogos.NOTAS_DEBITO) == set(modelo.NOTAS_DEBITO)
    assert catalogos.NOTAS == catalogos.NOTAS_CREDITO | catalogos.NOTAS_DEBITO == set(modelo.NOTAS)
    # Y todo código con catálogo es una nota, y toda nota tiene catálogo: sin huérfanos por ningún lado.
    assert {t for t in catalogos.TIPOS_CP if catalogos.motivos_de_nota(t)} == set(catalogos.NOTAS)


def test_los_motivos_de_nota_salen_por_la_fachada_con_su_fuente():
    """Un ERP los lee por la API o por el recurso del MCP, no copiándolos."""
    catalogos_sunat = api.catalogos_sunat()
    assert catalogos_sunat["motivos_nota_credito"] == catalogos.MOTIVOS_NOTA_CREDITO
    assert catalogos_sunat["motivos_nota_debito"] == catalogos.MOTIVOS_NOTA_DEBITO
    # La fuente dice la norma Y el asunto; el número de catálogo vive dentro de la cita, no en el nombre.
    for nombre, norma in (("motivos_nota_credito", "193-2020"), ("motivos_nota_debito", "318-2017")):
        fuente = catalogos_sunat["fuentes"][nombre]
        assert norma in fuente and "nota de" in fuente.lower()


# ── El Catálogo 05: los códigos de tributo ─────────────────────────────────────────────────────────────────────
#
# Hasta la 5.0 eran nueve constantes del módulo **sin fuente y sin un solo test**: la superficie pública congela sus
# NOMBRES pero no sus VALORES, así que cambiar `TRIBUTO_IGV` de `"1000"` a cualquier otra cosa pasaba verde y el
# lector de XML repartía los importes del comprobante en los campos equivocados sin que nada se quejara. Es el mismo
# agujero que las tres cifras del IGV tuvieron hasta la 2.8.
#
# Los diez salen del Anexo II de la RS 244-2019, leído: el `3000` y el `7152` no estaban en la deducción original.

TRIBUTOS_DEL_ANEXO = {
    "1000": "IGV Impuesto General a las Ventas",
    "1016": "Impuesto a la Venta Arroz Pilado",
    "2000": "ISC Impuesto Selectivo al Consumo",
    "3000": "Impuesto a la Renta",
    "7152": "Impuesto al Consumo de las bolsas de plástico",
    "9995": "Exportación",
    "9996": "Gratuito",
    "9997": "Exonerado",
    "9998": "Inafecto",
    "9999": "Otros tributos",
}


def test_los_codigos_de_tributo_son_los_del_anexo():
    """Con su orden, que es el del anexo: el código ordena la tabla y el `3000` va entre el ISC y el ICBPER."""
    assert list(catalogos.TRIBUTOS.items()) == list(TRIBUTOS_DEL_ANEXO.items())
    assert api.catalogos_sunat()["tributos"] == TRIBUTOS_DEL_ANEXO


def test_cada_constante_de_tributo_apunta_a_su_fila():
    """Los nueve nombres de siempre, más el `3000` que entró con la tabla. Son los que `lectores/xml_ubl.py` usa para
    repartir los importes del XML, así que un valor cambiado manda el IGV a la columna del ISC."""
    esperado = {"TRIBUTO_IGV": "1000", "TRIBUTO_IVAP": "1016", "TRIBUTO_ISC": "2000", "TRIBUTO_RENTA": "3000",
                "TRIBUTO_ICBPER": "7152", "TRIBUTO_EXPORTACION": "9995", "TRIBUTO_GRATUITO": "9996",
                "TRIBUTO_EXONERADO": "9997", "TRIBUTO_INAFECTO": "9998", "TRIBUTO_OTROS": "9999"}
    for nombre, codigo in esperado.items():
        assert getattr(catalogos, nombre) == codigo, nombre
        assert codigo in catalogos.TRIBUTOS, f"{nombre} apunta a una fila que la tabla no tiene"


def test_los_tributos_salen_por_la_fachada_con_su_fuente():
    """Y la fuente dice la norma Y el asunto, como las de los medios de pago y los motivos de nota. Era el único
    catálogo de SUNAT del motor que no citaba ninguna: ni resolución, ni anexo, ni URL."""
    fuente = api.catalogos_sunat()["fuentes"]["tributos"]
    assert "RS 097-2012" in fuente and "RS 244-2019" in fuente
    assert "tributos" in fuente.lower() and "sunat.gob.pe" in fuente


def test_el_catalogo_05_no_son_solo_tributos():
    """Su nombre lo dice —«tipos de tributos Y OTROS CONCEPTOS»— y el motor lo trata así: del `9996` gratuito solo
    toma la base y la manda a `datos_originales`, nunca a un campo del comprobante. Confundir las dos mitades es
    contar como impuesto lo que es la condición de la operación."""
    assert all(c in catalogos.TRIBUTOS for c in
               (catalogos.TRIBUTO_EXPORTACION, catalogos.TRIBUTO_GRATUITO, catalogos.TRIBUTO_EXONERADO,
                catalogos.TRIBUTO_INAFECTO))
    assert catalogos.TRIBUTOS[catalogos.TRIBUTO_RENTA] == "Impuesto a la Renta"


# ── Las tres cifras del IGV ────────────────────────────────────────────────────────────────────────────────────
#
# No las fijaba nadie: un grep de `TASA_IGV`, `TASAS_IGV_REDUCIDAS` y `TOLERANCIA_IGV` sobre `tests/` daba cero
# hasta la 2.8. Son las tres de las que depende que el IGV cuadre —`validar` decide con ellas `IGV_NO_CUADRA` y
# `IGV_TASA_REDUCIDA`, e `igv.tasa_legal` reconoce con ellas la tasa que un registro declara—, así que cambiar
# cualquiera movería silenciosamente lo que el motor acepta y lo que escribe CONTASIS en su columna del IGV.

TASA_IGV_DE_LA_1_0 = "0.18"
TASAS_REDUCIDAS_DE_LA_1_0 = ("0.10", "0.105", "0.08")   # restaurantes y hoteles; se aceptan con aviso, no con error
TOLERANCIA_DE_LA_1_0 = Decimal("0.05")                  # cinco céntimos, en unidades de IMPORTE y no de tasa


def test_las_tasas_de_igv_son_las_de_la_1_0():
    """Son fracciones escritas como texto (`"0.18"`, no `18`): quien las use las multiplica por 100 para el
    porcentaje. Cambiar el tipo rompería tanto a `validar` como a `igv.tasa_legal`."""
    assert catalogos.TASA_IGV == TASA_IGV_DE_LA_1_0
    assert catalogos.TASAS_IGV_REDUCIDAS == TASAS_REDUCIDAS_DE_LA_1_0
    assert all(isinstance(t, str) for t in (catalogos.TASA_IGV, *catalogos.TASAS_IGV_REDUCIDAS))


def test_la_tolerancia_del_igv_es_la_de_la_1_0():
    """Vivía en `validar.py` y la leía también `igv.py`, que por eso dependía de la validación entera. Es la MISMA
    para las dos, y que lo sea es lo que hace que `igv.tasa_legal` reconozca exactamente las tasas que `validar`
    acepta: si se separaran, un comprobante podría declarar 18 % en el registro y ser `IGV_NO_CUADRA` a la vez."""
    assert catalogos.TOLERANCIA_IGV == TOLERANCIA_DE_LA_1_0
    assert isinstance(catalogos.TOLERANCIA_IGV, Decimal)
    from contaperu import igv, validar
    assert igv.TOLERANCIA is validar.TOLERANCIA is catalogos.TOLERANCIA_IGV


def test_la_tasa_general_y_las_reducidas_no_se_pisan():
    """Un duplicado haría que `igv.tasa_legal` devolviera la primera que cuadre y nadie lo notaría."""
    todas = (catalogos.TASA_IGV, *catalogos.TASAS_IGV_REDUCIDAS)
    assert len(set(todas)) == len(todas)
