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
    assert set(datos) == {"tipos_comprobante", "tipos_documento_identidad", "monedas", "medios_pago"}
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
