"""Los datos del driver CONTASIS, y nada más: sus columnas, sus largos y sus reglas de formato, cada una con su fuente.

Las fuentes son dos, y las dos viven fuera de Git, en `tests/fixtures/privado/contasis/`:

- **La plantilla oficial**, «FORMATO REGISTRO DE COMPRAS / VENTAS - SISTEMA EXPERTO CONTABLE 26.00 - NewContaSis».
  Sus filas 10-13 dan cada columna y su largo, y los comentarios de sus cabeceras son la documentación oficial que
  hay: la guía web de Contasiscorp no respondía el 12-sep-2026.
- **Un registro de compras y uno de ventas que CONTASIS importó**, de un mes real de 2026, revisados con John el
  12-sep-2026. De ellos salen el tipo de cada celda y cómo va una columna vacía.
"""
from __future__ import annotations

from ...formato import Opciones

NOMBRE = "contasis"
FORMATOS = {"compra": "contasis_xlsx", "venta": "contasis_xlsx"}
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OPCIONES = Opciones(extension=".xlsx")
# El recibo por honorarios no va en este archivo (John, 12-sep-2026): la plantilla de compras no tiene dónde llevar
# su retención de 4ta.
EXCLUYE_TIPOS = frozenset({"02"})
# CONTASIS arma un asiento por fila con UNA cuenta de la base (John, 12-sep-2026): un reparto entre cuentas no sale.
EXIGE = frozenset({"cuenta_unica"})

# La pestaña conserva su nombre, y el archivo va sin las filas 1-13 de la plantilla: su nota 3 dice «Eliminar la Fila
# 1 a 13 dejando solo los ingresos realizados» (John, 12-sep-2026: «el mismo formato lo dice»).
HOJAS = {"compra": "FORMATO_COMPRAS", "venta": "FORMATO_VENTAS"}

TEXTO, FECHA, IMPORTE, CAMBIO, PORCENTAJE, NUMERO = "texto", "fecha", "importe", "cambio", "porcentaje", "numero"

# (letra, columna, clase, largo), de las filas 10-13 de la plantilla. El largo es el de los textos (y el del régimen
# especial, «1 NUMERICO»). `tests/test_plantilla_contasis.py` los compara con la plantilla, uno por uno.
COMPRAS: tuple[tuple[str, str, str, int], ...] = (
    ("A", "Fecha de emisión del comprobante", FECHA, 0),
    ("B", "Fecha de vencimiento o fecha de pago", FECHA, 0),
    ("C", "Tipo de comprobante", TEXTO, 2),
    ("D", "Serie o código de la dependencia aduanera", TEXTO, 6),
    ("E", "Año de emisión de la DUA o DSI", TEXTO, 4),
    ("F", "Número del comprobante", TEXTO, 13),
    ("G", "Tipo de documento del proveedor", TEXTO, 1),
    ("H", "Número de documento del proveedor", TEXTO, 11),
    ("I", "Apellidos y nombres, denominación o razón social", TEXTO, 60),
    ("J", "Base imponible: gravadas destinadas a operaciones gravadas", IMPORTE, 0),
    ("K", "IGV: gravadas destinadas a operaciones gravadas", IMPORTE, 0),
    ("L", "Base imponible: gravadas destinadas a gravadas y no gravadas", IMPORTE, 0),
    ("M", "IGV: gravadas destinadas a gravadas y no gravadas", IMPORTE, 0),
    ("N", "Base imponible: gravadas destinadas a no gravadas", IMPORTE, 0),
    ("O", "IGV: gravadas destinadas a no gravadas", IMPORTE, 0),
    ("P", "Valor de las adquisiciones no gravadas", IMPORTE, 0),
    ("Q", "ISC", IMPORTE, 0),
    ("R", "Otros tributos y cargos", IMPORTE, 0),
    ("S", "Importe total", IMPORTE, 0),
    ("T", "Nº de comprobante emitido por sujeto no domiciliado", TEXTO, 20),
    ("U", "Constancia de depósito de detracción: número", TEXTO, 20),
    ("V", "Constancia de depósito de detracción: fecha", FECHA, 0),
    ("W", "Tipo de cambio", CAMBIO, 0),
    ("X", "Documento que modifica: fecha", FECHA, 0),
    ("Y", "Documento que modifica: tipo", TEXTO, 2),
    ("Z", "Documento que modifica: serie", TEXTO, 6),
    ("AA", "Documento que modifica: número", TEXTO, 13),
    ("AB", "Moneda", TEXTO, 1),
    ("AC", "Equivalente en dólares americanos", IMPORTE, 0),
    ("AD", "Fecha de vencimiento", FECHA, 0),
    ("AE", "Condición contado/crédito", TEXTO, 3),
    ("AF", "Cuenta contable de la base imponible", TEXTO, 10),
    ("AG", "Cuenta contable de otros tributos y cargos", TEXTO, 10),
    ("AH", "Cuenta contable del total", TEXTO, 10),
    ("AI", "Código de centro de costos", TEXTO, 9),
    ("AJ", "Código de centro de costos 2", TEXTO, 9),
    ("AK", "Régimen especial", NUMERO, 1),
    ("AL", "Porcentaje del régimen especial", PORCENTAJE, 0),
    ("AM", "Importe del régimen especial", IMPORTE, 0),
    ("AN", "Serie del documento del régimen especial", TEXTO, 6),
    ("AO", "Número del documento del régimen especial", TEXTO, 13),
    ("AP", "Fecha del documento del régimen especial", FECHA, 0),
    ("AQ", "Código de presupuesto", TEXTO, 10),
    ("AR", "Porcentaje del IGV", PORCENTAJE, 0),
    ("AS", "Glosa", TEXTO, 60),
    ("AT", "Condición de percepción", TEXTO, 1),
    ("AU", "Importe para el cálculo del régimen especial", IMPORTE, 0),
    ("AV", "Clasificación de bienes y servicios adquiridos", TEXTO, 1),
    ("AW", "Impuesto al consumo de las bolsas de plástico", IMPORTE, 0),
    ("AX", "Cuenta contable del ICBPER", TEXTO, 10),
)

VENTAS: tuple[tuple[str, str, str, int], ...] = (
    ("A", "Fecha de emisión del comprobante", FECHA, 0),
    ("B", "Fecha de vencimiento o fecha de pago", FECHA, 0),
    ("C", "Tipo de comprobante", TEXTO, 2),
    ("D", "Nº de serie o nº de serie de la máquina registradora", TEXTO, 6),
    ("E", "Número del comprobante", TEXTO, 13),
    ("F", "Tipo de documento del cliente", TEXTO, 1),
    ("G", "Número de documento del cliente", TEXTO, 11),
    ("H", "Apellidos y nombres, denominación o razón social", TEXTO, 60),
    ("I", "Valor facturado de la exportación", IMPORTE, 0),
    ("J", "Base imponible de la operación gravada", IMPORTE, 0),
    ("K", "Importe de la operación exonerada", IMPORTE, 0),
    ("L", "Importe de la operación inafecta", IMPORTE, 0),
    ("M", "ISC", IMPORTE, 0),
    ("N", "IGV y/o IPM", IMPORTE, 0),
    ("O", "Otros tributos y cargos que no forman parte de la base imponible", IMPORTE, 0),
    ("P", "Importe total del comprobante", IMPORTE, 0),
    ("Q", "Tipo de cambio", CAMBIO, 0),
    ("R", "Documento que modifica: fecha", FECHA, 0),
    ("S", "Documento que modifica: tipo", TEXTO, 2),
    ("T", "Documento que modifica: serie", TEXTO, 6),
    ("U", "Documento que modifica: número", TEXTO, 13),
    ("V", "Moneda", TEXTO, 1),
    ("W", "Equivalente en dólares americanos", IMPORTE, 0),
    ("X", "Fecha de vencimiento", FECHA, 0),
    ("Y", "Condición contado/crédito", TEXTO, 3),
    ("Z", "Código de centro de costos", TEXTO, 9),
    ("AA", "Código de centro de costos 2", TEXTO, 9),
    ("AB", "Cuenta contable de la base imponible", TEXTO, 10),
    ("AC", "Cuenta contable de otros tributos y cargos", TEXTO, 10),
    ("AD", "Cuenta contable del total", TEXTO, 10),
    ("AE", "Régimen especial", NUMERO, 1),
    ("AF", "Porcentaje del régimen especial", PORCENTAJE, 0),
    ("AG", "Importe del régimen especial", IMPORTE, 0),
    ("AH", "Serie del documento del régimen especial", TEXTO, 6),
    ("AI", "Número del documento del régimen especial", TEXTO, 13),
    ("AJ", "Fecha del documento del régimen especial", FECHA, 0),
    ("AK", "Código de presupuesto", TEXTO, 10),
    ("AL", "Porcentaje del IGV", PORCENTAJE, 0),
    ("AM", "Glosa", TEXTO, 60),
    ("AN", "Medio de pago", TEXTO, 3),
    ("AO", "Condición de percepción", TEXTO, 1),
    ("AP", "Importe para el cálculo del régimen especial", IMPORTE, 0),
    ("AQ", "Impuesto al consumo de las bolsas de plástico", IMPORTE, 0),
    ("AR", "Cuenta contable del ICBPER", TEXTO, 10),
)

COLUMNAS = {"compra": COMPRAS, "venta": VENTAS}

# Los formatos de celda del registro validado: la fecha con el formato 14 de Excel (la fecha corta del sistema), los
# importes y porcentajes con dos decimales, el tipo de cambio con cuatro y los textos como texto.
FORMATO_CELDA = {TEXTO: "@", FECHA: "mm-dd-yy", IMPORTE: "#,##0.00", PORCENTAJE: "#,##0.00",
                 CAMBIO: "#,##0.0000", NUMERO: "0"}

# Los textos van rellenos con espacios hasta su largo, también los vacíos: CONTASIS lo exige (John, 12-sep-2026) y
# así viene el registro validado. Las excepciones salen del mismo registro: el nombre va de corrido, sin relleno;
# el nombre y la glosa, que son texto libre, se cortan a su largo; y unas pocas columnas vacías van como celda vacía.
SE_CORTAN = {"compra": frozenset({"I", "AS"}), "venta": frozenset({"H", "AM"})}
SIN_RELLENO = {"compra": frozenset({"I"}), "venta": frozenset({"H"})}
VACIAS_SIN_ESPACIOS = {"compra": frozenset({"AT", "AV", "AX"}), "venta": frozenset({"AO", "AR"})}

# El total y el IGV de cada registro: la diferencia del redondeo de los dólares la absorbe la base, nunca el IGV.
TOTAL = {"compra": "S", "venta": "P"}
COLUMNAS_IGV = {"compra": frozenset({"K", "M", "O"}), "venta": frozenset({"N"})}

# Comentarios de la plantilla: «NUEVOS SOLES (S) / DOLARES AMERICANOS (D)» y «Contado (CON) / Crédito (CRE)».
MONEDAS = {"PEN": "S", "USD": "D"}
CONDICIONES = {"contado": "CON", "credito": "CRE"}
# Un documento que no dice su condición va de contado: así llevan todas sus filas los dos registros validados.
CONDICION_SIN_DATO = "CON"
# Medio de pago de ventas (la tabla del comentario de la plantilla): el del entorno, en la configuración
# (`medio_pago`); si no lo tiene, 001 «depósito en cuenta», el de todas las filas del registro validado.
MEDIO_PAGO_DE_FABRICA = "001"

# Lo que el registro de CONTASIS no puede llevar (`no_caben`): cada motivo se lee detrás de un número.
MOTIVOS = {
    "moneda": "en una moneda que CONTASIS no admite (solo soles y dólares)",
    "cambio": "en dólares sin tipo de cambio, que CONTASIS necesita para llevarlos a soles",
    "rango": "de un rango de boletas, que el registro de CONTASIS no tiene cómo numerar",
    "ivap": "con IVAP, que el registro de CONTASIS no tiene dónde llevar",
    "largo": "con un código más largo que su columna de CONTASIS (serie, número, documento, cuenta o centro)",
}
