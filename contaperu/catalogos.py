"""Catálogos de SUNAT que usa el motor (los que hacen falta, no todos).

Fuentes: Anexo 1 de la RS 112-2021 (Tabla 1 documentos de identidad, Tabla 2
monedas, Tabla 3 tipos de comprobante del RVIE) y Anexo 1 de la RS 040-2022
(Tabla 11 tipos de comprobante del RCE). Los códigos de tributo (1000, 9997…)
son el Catálogo 05 de la factura electrónica (UBL 2.1).
"""
from __future__ import annotations

# Tipo de comprobante (2 dígitos). Se listan los que un estudio contable ve de verdad.
TIPOS_CP: dict[str, str] = {
    "00": "Otros",
    "01": "Factura",
    "02": "Recibo por honorarios",
    "03": "Boleta de venta",
    "04": "Liquidación de compra",
    "05": "Boleto de transporte aéreo",
    "06": "Carta de porte aéreo",
    "07": "Nota de crédito",
    "08": "Nota de débito",
    "09": "Guía de remisión",
    "10": "Recibo por arrendamiento",
    "12": "Ticket de máquina registradora",
    "13": "Documento de bancos y financieras",
    "14": "Recibo de servicios públicos",
    "16": "Boleto de transporte público",
    "18": "Documento de AFP",
    "21": "Conocimiento de embarque",
    "22": "Comprobante por operaciones no habituales",
    "25": "Operadores de contratos de colaboración",
    "36": "Documento de peaje",
    "46": "Constancia de pago (SUNAT)",
    "50": "DUA importación definitiva",
    "52": "Despacho simplificado de importación",
    "87": "Nota de crédito especial",
    "88": "Nota de débito especial",
    "91": "Comprobante de no domiciliado",
    "97": "Nota de crédito de no domiciliado",
    "98": "Nota de débito de no domiciliado",
}

# Comprobantes en los que SUNAT exige fecha de vencimiento o de pago (RCE campo 6).
EXIGEN_VENCIMIENTO = frozenset({"14", "46", "50", "51", "52", "53", "54"})
# Comprobantes en los que el ICBPER va con 0.00 aunque no aplique (nunca vacío).
# Notas: llevan documento modificado obligatorio.
NOTAS = frozenset({"07", "08", "87", "88"})
# Comprobantes aduaneros: llevan año de la DUA y código de dependencia.
ADUANEROS = frozenset({"50", "51", "52", "53", "54"})
# Comprobantes que pueden ir sin documento de la contraparte (consumidor final).
SIN_CONTRAPARTE_OK = frozenset({"03", "12", "13", "16", "36", "00"})
# Comprobantes que NO se anotan en el registro que se declara a SUNAT (el SIRE):
# el recibo por honorarios (02) — regla de contabilidad. SÍ entran
# al asiento contable (Excel de CONCAR, sub-diario 15): son gasto de la empresa.
# Se filtran en `generar()` según lo que declare cada driver (`EXCLUYE_TIPOS`).
FUERA_DEL_REGISTRO_SUNAT = frozenset({"02"})

# Tipos con un tratamiento propio en el asiento: el recibo por honorarios (su cuenta y su retención de 4ta), la boleta
# (su registro), la nota de crédito (invierte el asiento) y las notas (llevan el documento que modifican).
TIPO_HONORARIOS, TIPO_BOLETA, TIPOS_INVIERTEN, TIPOS_NOTA = "02", "03", ("07",), ("07", "08")

# Tabla 1: tipo de documento de identidad.
TIPOS_DOC_IDENTIDAD: dict[str, str] = {
    "0": "Otros",
    "1": "DNI",
    "4": "Carné de extranjería",
    "6": "RUC",
    "7": "Pasaporte",
    "A": "Cédula diplomática",
}

# Tabla 2 (ISO 4217). Se deja pasar cualquier código de 3 letras; estos son los habituales.
MONEDAS = frozenset({"PEN", "USD", "EUR", "CNY", "GBP", "JPY", "CLP", "COP", "BRL", "MXN"})

# Catálogo 05 de la factura electrónica: código de tributo en cac:TaxScheme/cbc:ID.
TRIBUTO_IGV = "1000"
TRIBUTO_IVAP = "1016"
TRIBUTO_ISC = "2000"
TRIBUTO_ICBPER = "7152"
TRIBUTO_EXPORTACION = "9995"
TRIBUTO_GRATUITO = "9996"   # operaciones gratuitas: NO entran en el cuadre ni en el registro
TRIBUTO_EXONERADO = "9997"
TRIBUTO_INAFECTO = "9998"
TRIBUTO_OTROS = "9999"

# Tasas de IGV que la validación reconoce. La general es 18 %; las reducidas
# (restaurantes y hoteles) se aceptan con aviso, no como error.
TASA_IGV = "0.18"
TASAS_IGV_REDUCIDAS = ("0.10", "0.105", "0.08")

# schemeID del Catálogo 06 → Tabla 1 (coinciden salvo matices).
SCHEME_A_TIPO_DOC = {"0": "0", "1": "1", "4": "4", "6": "6", "7": "7", "A": "A", "-": "0"}


def ruc_valido(ruc: str) -> bool:
    """Módulo 11 de SUNAT: factores 5,4,3,2,7,6,5,4,3,2 sobre los 10 primeros dígitos."""
    if not (isinstance(ruc, str) and len(ruc) == 11 and ruc.isdigit()):
        return False
    if ruc[:2] not in ("10", "15", "16", "17", "20"):
        return False
    factores = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    suma = sum(int(d) * f for d, f in zip(ruc[:10], factores))
    resto = 11 - (suma % 11)
    verificador = {10: 0, 11: 1}.get(resto, resto)
    return verificador == int(ruc[10])



