"""Los catálogos de SUNAT viven en datos, con su fuente (1.1, primer paso del hito C1).

Moverlos del código a `datos/sunat/catalogos.json` no puede cambiar ni un código ni un nombre: los valores de la 1.0
quedan escritos aquí, tal como estaban en `catalogos.py`.
"""
from __future__ import annotations

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
