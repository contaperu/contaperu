"""Los catálogos de un comprobante —tipos, documentos de identidad, monedas, medios de pago, motivos de
nota— y las reglas del motor sobre esos códigos.

Van juntos a propósito: una regla como «el 87 es la nota de crédito del no domiciliado» no se entiende sin el
catálogo del que sale el 87, y separarlas obligaría a ir a dos sitios para leer una sola cosa.
"""
from __future__ import annotations

from ._fuente import CATALOGOS

TIPOS_CP: dict[str, str] = dict(CATALOGOS["tipos_comprobante"]["codigos"])

# Comprobantes en los que SUNAT exige fecha de vencimiento o de pago (RCE campo 6).
EXIGEN_VENCIMIENTO = frozenset({"14", "46", "50", "51", "52", "53", "54"})
# Comprobantes en los que el ICBPER va con 0.00 aunque no aplique (nunca vacío).
# Notas: llevan documento modificado obligatorio. Se separan en crédito y débito porque su catálogo de motivos es
# distinto —el 09 y el 10— y porque el «01» significa cosas opuestas en cada uno; `NOTAS` se DERIVA de los dos, así
# que aquí no se pueden desacordar. Los mismos cuatro códigos viven en `modelo.NOTAS_CREDITO`/`NOTAS_DEBITO`: los dos
# módulos son hojas y no se importan entre sí, así que lo que impide que se separen es un test
# (`test_catalogos.py::test_las_dos_listas_de_notas_dicen_lo_mismo`), no la buena voluntad.
NOTAS_CREDITO = frozenset({"07", "87"})     # 07 domiciliado · 87 no domiciliado
NOTAS_DEBITO = frozenset({"08", "88"})      # las hermanas que suman
NOTAS = NOTAS_CREDITO | NOTAS_DEBITO
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

# Tipo de documento de identidad (Anexo 1 de la RS 112-2021).
TIPOS_DOC_IDENTIDAD: dict[str, str] = dict(CATALOGOS["tipos_documento_identidad"]["codigos"])

# Monedas, ISO 4217 (Anexo 1 de la RS 112-2021). Se deja pasar cualquier código de 3 letras; estos son los
# habituales.
MONEDAS = frozenset(CATALOGOS["monedas"]["codigos"])

# Tipo de medio de pago (Anexo 3 de la RS 169-2015): los 22 códigos con los que se paga una operación, `001`
# depósito en cuenta … `999` otros. Son los medios del artículo 5 de la Ley 28194, la de bancarización.
#
# El motor no decide con ella: es vocabulario. Da significado al código que un sistema contable exige —CONTASIS lo
# pide en su registro de ventas— y permite avisar de uno que no existe. Un código que no esté aquí **no bloquea**
# (`validar.MEDIO_PAGO_DESCONOCIDO` es aviso): el día que SUNAT añada uno, nadie se queda sin exportar su mes.
MEDIOS_PAGO: dict[str, str] = dict(CATALOGOS["medios_pago"]["codigos"])

# Por qué se emitió una nota: el Catálogo 09 para las de crédito (13 motivos, «01 anulación de la operación» …
# «09 disminución en el valor») y el 10 para las de débito (3: mora, aumento de valor, penalidades).
#
# **Son dos tablas y no una porque los códigos colisionan**: el `01` es «anulación de la operación» en el de crédito
# e «intereses por mora» en el de débito. Juntarlas obligaría a inventar un prefijo, y un catálogo con códigos
# inventados deja de ser el de SUNAT.
#
# No son del SIRE: son de la factura electrónica (el `cbc:ResponseCode` del XML), y el SIRE los CITA —campo 34 del
# Anexo N.° 2 de la RS 112-2021 en ventas, campo 39 del Anexo 8 de la RS 040-2022 en compras—. Como los medios de
# pago, esto es vocabulario y el motor no decide con él: un código que no esté aquí **no bloquea**
# (`validar.TIPO_NOTA_DESCONOCIDO` es aviso), porque SUNAT ya le añadió cuatro códigos al 09 en 2020.
#
# Y OJO con lo que NO dice el `01` del Catálogo 09: dice que la nota **anula el comprobante que referencia**, no que
# la nota esté anulada. En el mes real con el que se hizo esto, las cinco notas con motivo `01` estaban vivas y con
# importes, y las dos que SUNAT daba de baja llevaban motivo `09`. Ninguna regla del motor lee el motivo para hablar
# de anulación.
MOTIVOS_NOTA_CREDITO: dict[str, str] = dict(CATALOGOS["motivos_nota_credito"]["codigos"])
MOTIVOS_NOTA_DEBITO: dict[str, str] = dict(CATALOGOS["motivos_nota_debito"]["codigos"])


def motivos_de_nota(tipo_cp: str) -> dict[str, str]:
    """El catálogo de motivos que le toca a ese comprobante, y `{}` si no es una nota.

    Aquí vive, **una sola vez**, el reparto entre los dos catálogos, y se apoya en los conjuntos completos: mirar
    solo `("07", "08")` dejaría al 87 y al 88 sin catálogo **en silencio**, que es exactamente la forma del fallo que
    `resumen.py` cuenta en su cabecera (una nota de crédito de no domiciliado tratada como si no lo fuera)."""
    codigo = str(tipo_cp or "").strip()
    if codigo in NOTAS_CREDITO:
        return MOTIVOS_NOTA_CREDITO
    if codigo in NOTAS_DEBITO:
        return MOTIVOS_NOTA_DEBITO
    return {}


# Código de tributo del XML de la factura electrónica, en `cac:TaxCategory/cac:TaxScheme/cbc:ID`: el Catálogo 05 del
# Anexo N.° 8, que **entra en datos con su fuente en la 5.0** y hasta entonces era lo único de este módulo que
# afirmaba códigos de SUNAT sin citar la norma de la que salen —ni en `FUENTES`, ni en la fachada, ni con un test que
# fijara un solo valor—. Su `fuente` dice de qué anexo se transcribió y qué columna se dejó fuera.
#
# Los nueve nombres de siempre se quedan **leyendo de la tabla**: están en la superficie pública congelada y nunca
# avisaron de que fueran a irse, así que retirarlos rompería la promesa de que lo que se retira avisa durante toda la
# mayor anterior. `TRIBUTO_RENTA` es nuevo: el `3000` estaba en el anexo y no en el motor, y es el tributo que la
# línea de rol `retencion` cita en su bloque.


# schemeID del Catálogo 06 → tipo de documento de identidad (coinciden salvo matices).
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
