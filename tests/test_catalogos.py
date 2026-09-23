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
    assert set(datos) == {"tipos_comprobante", "tipos_documento_identidad", "monedas"}
    assert all(tabla["fuente"].strip() for tabla in datos.values())
    assert catalogos.TIPOS_CP == datos["tipos_comprobante"]["codigos"]
    assert catalogos.FUENTES == {nombre: tabla["fuente"] for nombre, tabla in datos.items()}
    assert api.catalogos_sunat()["fuentes"] == catalogos.FUENTES


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
