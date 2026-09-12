"""Los DATOS de la plantilla CONCAR: identidad, defaults configurables por
cuenta/RUC, y la cabecera literal del Excel oficial (41 columnas, verificada
celda a celda contra `plantilla-concar.xlsx` el 23-ago-2026).

Aquí no hay lógica: si CONCAR cambia una columna o SUNAT un catálogo, se toca
este archivo y nada más.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..formato import Opciones

NOMBRE = "concar"
OPCIONES = Opciones(fecha="DD/MM/AAAA", extension=".xlsx")
FORMATOS = {"compra": "concar_xlsx", "venta": "concar_xlsx"}
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Lo que CONCAR no puede importar sin (contrato de driver, `EXIGE`): el centro de costo en las cuentas
# que lo llevan en la columna M —el contador, 06-sep-2026: obligatorio donde de verdad se escribe— y
# una moneda con código en su Tabla General 03 (solo MN y US). Desde el 11-sep-2026 lo hace cumplir el
# propio driver; hasta entonces solo lo avisaba `diagnosticar` y lo negaba el portal por su cuenta.
EXIGE = frozenset({"centro_costo", "moneda"})

# La línea de la detracción, calcada del Excel real que CONCAR ACEPTÓ (set-2026): tipo de documento
# **DR** y el comodín del número —la constancia del depósito no se conoce al provisionar, se paga
# días después—. El `DT` que hubo hasta entonces salía del borrador de la plantilla y nunca llegó a
# importarse en un CONCAR de verdad; el archivo validado dice DR. Es la sigla de la Tabla General 06,
# que cada contribuyente numera a su gusto: por eso `detraccion_tipo_doc` puede cambiarla.
TIPO_DOC_DETRACCION = "DR"
NUMERO_DETRACCION_PENDIENTE = "9999999999"

# ── Valores por defecto (manual de asientos de referencia; sobreescribibles por RUC) ──
# `cuentas.gasto` va VACÍO a propósito: en la práctica es el comodín "63/65", que no es
# una cuenta. Aquí la pone la fila (`cuenta_contable`) o el RUC (`config.concar.cuentas.gasto`).
DEFAULTS: dict[str, Any] = {
    "cuentas": {
        "gasto": "",
        "cxp": {"PEN": "421201", "USD": "421202"},          # facturas por pagar: soles / dólares
        # La factura afecta a detracción (SUNAT) lleva su propia cuenta por pagar, la MISMA en las dos
        # monedas (regla de contabilidad). Editable en la configuración del contribuyente.
        "cxp_detraccion": {"PEN": "421203", "USD": "421203"},
        "honorarios": {"PEN": "424101", "USD": "424102"},   # recibos por honorarios por pagar
        "retencion_4ta": "401721",                           # tributos por pagar: renta de 4ta retenida (cuenta habitual, 23-ago-2026)
        "igv": "401111",                                     # IGV (crédito fiscal en compras, débito en ventas)
        "clientes": {"PEN": "121201", "USD": "121202"},      # ventas: cuentas por cobrar
        "ventas": "701101",                                   # ventas: ingreso (el habitual)
    },
    # Código SUNAT (Tabla 10) → {sigla de CONCAR (columna R, T.G. 06), sub-diario}. Los habituales:
    # 11 compras, 13 boletas, 15 honorarios (y 10 para la factura con detracción, ver abajo). Los
    # demás tipos de la Tabla 10 NO están a propósito: cada CONCAR tiene su T.G. 06 → por RUC.
    # Desde el 29-ago-2026 los sub-diarios se gobiernan POR USO (sub_diario_compras /
    # _ventas / _detraccion y los dos tipos con registro propio): un tipo solo lleva
    # `sub_diario` aquí cuando su registro ES otro (boletas, honorarios). Un
    # `tipos.NN.sub_diario` puesto por el estudio en su jsonb sigue ganando al general.
    "tipos": {
        "01": {"concar": "FT"},                       # Factura
        "02": {"concar": "RH", "sub_diario": "15"},   # Recibo por honorarios
        "03": {"concar": "BV", "sub_diario": "13"},   # Boleta de venta
        "05": {"concar": "BA"},                       # Boleto aéreo
        "07": {"concar": "NC"},                       # Nota de crédito
        "08": {"concar": "ND"},                       # Nota de débito
        "12": {"concar": "TK"},                       # Ticket
        "14": {"concar": "RC"},                       # Recibo de servicios públicos (regla de contabilidad)
    },
    # Columna E. CONCAR solo admite MN y US (rechaza ME). Otra moneda → se detiene la exportación.
    "monedas_codigo": {"PEN": "MN", "USD": "US"},
    # La factura afecta a detracción va a su propio sub-diario ('' = se queda en el de su tipo).
    "sub_diario_detraccion": "10",
    # En VENTAS todo va a un solo sub-diario (lo habitual: 05); la sigla (columna R) sigue saliendo de `tipos`.
    "sub_diario_ventas": "05",
    # El general de COMPRAS: facturas, tickets, notas y todo tipo sin registro propio.
    "sub_diario_compras": "11",
    # Código SUNAT del bien/servicio (3 dígitos, viene en el XML) → código interno de la T.G. 28
    # de CONCAR (5 dígitos: el de SUNAT + 2 propios). Un código que no esté aquí sale como
    # SUNAT + "01" (el patrón más común) hasta que el RUC lo configure.
    #
    # QUÉ ENTRA (los más usados, no todos): **todo el Anexo 3**
    # —los servicios, que son lo que un estudio ve a diario— más el transporte de bienes por vía
    # terrestre (027, su propio régimen) y las tres de bienes que aparecen en obra y comercio
    # (madera, arena y piedra, residuos). Fuera quedan las sectoriales (pesca, oro, minerales,
    # páprika, espárragos…): 38 filas para configurar espantan, y la que aparezca se añade.
    # Los siete que ya usaba un contribuyente real conservan su código interno EXACTO; los demás entran con
    # el patrón SUNAT + "01", editable en la pantalla.
    "detraccion_codigos": {"008": "00801", "009": "00901", "010": "01001", "012": "01201",
                           "019": "01903", "020": "02001", "021": "02101", "022": "02201",
                           "024": "02401", "025": "02501", "026": "02601", "027": "02702",
                           "030": "03001", "037": "03701"},
    # Tasa por código SUNAT, por si el comprobante no la trae. De los apéndices vigentes del SPOT
    # (orientacion.sunat.gob.pe), cruzados POR NOMBRE con el Catálogo 54: en esa página la columna
    # "código" es el numeral dentro del anexo, no el código del comprobante (ahí "14" es Leche,
    # que en el catálogo es 023, mientras 014 son Carnes). Cruzarlo por número sale mal.
    # La sigla de la Tabla General 06 con la que el sistema del contribuyente reconoce esta línea.
    # `DR` es la que aceptó un CONCAR real; se deja editable porque la T.G. 06 la numera cada empresa.
    "detraccion_tipo_doc": TIPO_DOC_DETRACCION,
    # El área (Tabla General 26) a la que CONCAR carga la línea de la detracción. **Vacía a
    # propósito**: es un número propio de cada empresa, no una constante contable, y ponerle uno de
    # fábrica metería los apuntes de todo el mundo en un área que nadie eligió. Solo se escribe en
    # la línea de la detracción, que es la única que la llevaba en el archivo validado.
    "detraccion_area": "",
    "detraccion_tasas": {"008": 4, "009": 10, "010": 15, "012": 12, "019": 10, "020": 12,
                         "021": 10, "022": 12, "024": 10, "025": 10, "026": 10, "027": 4,
                         "030": 4, "037": 12},
    # Nombre oficial (Catálogo 54 de SUNAT, Anexo N.° 8): la pantalla dice "030 · Contratos de
    # construcción" en vez de un código a secas — un número de tres dígitos no le dice nada a nadie.
    "detraccion_nombres": {"008": "Madera", "009": "Arena y piedra",
                           "010": "Residuos, subproductos, desechos, recortes y desperdicios",
                           "012": "Intermediación laboral y tercerización",
                           "019": "Arrendamiento de bienes muebles",
                           "020": "Mantenimiento y reparación de bienes muebles",
                           "021": "Movimiento de carga", "022": "Otros servicios empresariales",
                           "024": "Comisión mercantil", "025": "Fabricación de bienes por encargo",
                           "026": "Servicio de transporte de personas",
                           "027": "Servicio de transporte de bienes por vía terrestre",
                           "030": "Contratos de construcción",
                           "037": "Demás servicios gravados con el IGV"},
    # ¿Esta empresa lleva centros de costo (obras, proyectos, áreas)? Apagado, las
    # columnas M y X salen vacías aunque el comprobante traiga uno, y la aplicación que lo use
    # deja de pedirlo: hay CONCARs que no los usan.
    "usa_centros_costo": True,
    # QUÉ cuentas lo llevan, por PREFIJO (el contador, 09-sep-2026): «la cuenta 63 y 65 tiene
    # habilitado el centro de costo en la columna M, pero cuando es una cuenta 60 por defecto no
    # se debe asignar un centro de costo». En CONCAR esa marca vive en cada cuenta del plan, no
    # en un interruptor global; aquí se declara por prefijo, que es lo que un estudio sabe decir.
    # El `70` va incluido para que las VENTAS no cambien: el ingreso siempre llevó su centro en M.
    # Casa por `startswith`, igual que los mapeos del PCGE, así que "6311" también vale.
    # Lista VACÍA es una respuesta legítima (ninguna cuenta lo lleva) y no es lo mismo que
    # ausente (los tres de fábrica): ver `lleva_centro`.
    "cuentas_con_centro": ["63", "65", "70"],
    # El centro de costo va también en el anexo auxiliar (X) de la línea del proveedor ("doble anexo").
    "cc_en_anexo_auxiliar": True,
    # Y en las cuentas que NO lo llevan en M, el centro puede ir a la X de SU PROPIA línea, como
    # referencia: «algunas empresas optan en colocar la columna X como referencia el centro de
    # costo» (el contador, 09-sep-2026). Apagado de fábrica, y por dos motivos: es una opción y no
    # la norma, y la propia plantilla de CONCAR avisa de que X solo se llena «si Cuenta Contable
    # tiene seleccionado Tipo de Anexo Referencia» — escribirla donde no toca puede hacer que
    # rechace la importación. Es INDEPENDIENTE de `cc_en_anexo_auxiliar`, que es la X del tercero.
    "cc_referencia_en_x": False,
}
ETIQUETAS_SUB_DIARIO = {"05": "Ventas", "10": "Facturas con detracción", "11": "Facturas, tickets y notas",
                        "13": "Boletas de venta", "15": "Recibos por honorarios"}
TIPO_HONORARIOS, TIPO_BOLETA, TIPOS_INVIERTEN, TIPOS_NOTA = "02", "03", ("07",), ("07", "08")

TIPO_CONVERSION = "V"       # CONCAR busca el T.C. en su tabla; con T.C. en G pasa a 'C' (especial)
FLAG_CONVERSION = "S"
COLUMNAS_IMPORTE = ("O", "P", "Q", "AD", "AE", "AK", "AL")
COLUMNAS_FECHA = ("D", "J", "T", "U", "AB", "AH")
COLUMNAS_TEXTO = ("B", "C", "E", "F", "H", "I", "K", "L", "M", "N", "R", "S", "V", "W", "X", "Y", "Z", "AA", "AI")
D2 = Decimal("0.01")

# ── Encabezados de la plantilla oficial (literal; verificado contra plantilla-concar.xlsx) ──
EXCEL_HEADERS: dict[str, dict[str, str]] = {
    "row1": {
        "A": "WE", "B": "Sub Diario", "C": "Número de Comprobante", "D": "Fecha de Comprobante",
        "E": "Código de Moneda", "F": "Glosa Principal", "G": "Tipo de Cambio", "H": "Tipo de Conversión",
        "I": "Flag de Conversión de Moneda", "J": "Fecha Tipo de Cambio", "K": "Cuenta Contable",
        "L": "Código de Anexo", "M": "Código de Centro de Costo", "N": "Debe / Haber", "O": "Importe Original",
        "P": "Importe en Dólares", "Q": "Importe en Soles", "R": "Tipo de Documento", "S": "Número de Documento",
        "T": "Fecha de Documento", "U": "Fecha de Vencimiento", "V": "Código de Area", "W": "Glosa Detalle",
        "X": "Código de Anexo Auxiliar", "Y": "Medio de Pago", "Z": "Tipo de Documento de Referencia",
        "AA": "Número de Documento Referencia", "AB": "Fecha Documento Referencia",
        "AC": "Nro Máq. Registradora Tipo Doc. Ref.", "AD": "Base Imponible Documento Referencia",
        "AE": "IGV Documento Provisión", "AF": "Tipo Referencia en estado MQ", "AG": "Número Serie Caja Registradora",
        "AH": "Fecha de Operación", "AI": "Tipo de Tasa", "AJ": "Tasa Detracción/Percepción",
        "AK": "Importe Base Detracción/Percepción Dólares", "AL": "Importe Base Detracción/Percepción Soles",
        "AM": "Tipo Cambio para 'F'", "AN": "Importe de IGV sin derecho crédito fiscal", "AO": "Tasa IGV",
    },
    "row2": {
        "A": "Contabilidad", "B": "Ver T.G. 02",
        "C": "Los dos primeros dígitos son el mes y los otros 4 siguientes un correlativo",
        "E": "Ver T.G. 03",
        "G": "Llenar  solo si Tipo de Conversión es 'C'. Debe estar entre >=0 y <=9999.999999",
        "H": "Solo: 'C'= Especial, 'M'=Compra, 'V'=Venta , 'F' De acuerdo a fecha",
        "I": "Solo: 'S' = Si se convierte, 'N'= No se convierte",
        "J": "Si  Tipo de Conversión 'F'",
        "K": "Debe existir en el Plan de Cuentas",
        "L": "Si Cuenta Contable tiene seleccionado Tipo de Anexo, debe existir en la tabla de Anexos",
        "M": "Si Cuenta Contable tiene habilitado C. Costo, Ver T.G. 05",
        "N": "'D' ó 'H'",
        "O": "Importe original de la cuenta contable. Obligatorio, debe estar entre >=0 y <=99999999999.99",
        "P": "Importe de la Cuenta Contable en Dólares. Obligatorio si Flag de Conversión de Moneda esta en 'N', debe estar entre >=0 y <=99999999999.99",
        "Q": "Importe de la Cuenta Contable en Soles. Obligatorio si Flag de Conversión de Moneda esta en 'N', debe estra entre >=0 y <=99999999999.99",
        "R": "Si Cuenta Contable tiene habilitado el Documento Referencia Ver T.G. 06",
        "S": "Si Cuenta Contable tiene habilitado el Documento Referencia Incluye Serie y Número",
        "T": "Si Cuenta Contable tiene habilitado el Documento Referencia",
        "U": "Si Cuenta Contable tiene habilitada la Fecha de Vencimiento",
        "V": "Si Cuenta Contable tiene habilitada el Area. Ver T.G. 26",
        "X": "Si Cuenta Contable tiene seleccionado Tipo de Anexo Referencia",
        "Y": "Si Cuenta Contable tiene habilitado Tipo Medio Pago. Ver T.G. 'S1'",
        "Z": "Si Tipo de Documento es 'NA' ó 'ND' Ver T.G. 06",
        "AA": "Si Tipo de Documento es 'NC', 'NA' ó 'ND', incluye Serie y Número",
        "AB": "Si Tipo de Documento es 'NC', 'NA' ó 'ND'",
        "AC": "Si Tipo de Documento es 'NC', 'NA' ó 'ND'. Solo cuando el Tipo Documento de Referencia 'TK'",
        "AD": "Si Tipo de Documento es 'NC', 'NA' ó 'ND'",
        "AE": "Si Tipo de Documento es 'NC', 'NA' ó 'ND'",
        "AF": "Si la Cuenta Contable tiene Habilitado Documento Referencia 2 y  Tipo de Documento es 'TK'",
        "AG": "Si la Cuenta Contable teien Habilitado Documento Referencia 2 y  Tipo de Documento es 'TK'",
        "AH": "Si la Cuenta Contable tiene Habilitado Documento Referencia 2. Cuando Tipo de Documento es 'TK', consignar la fecha de emision del ticket",
        "AI": "Si la Cuenta Contable tiene configurada la Tasa:  Si es '1' ver T.G. 28 y '2' ver T.G. 29",
        "AJ": "Si la Cuenta Contable tiene conf. en Tasa:  Si es '1' ver T.G. 28 y '2' ver T.G. 29. Debe estar entre >=0 y <=999.99",
        "AK": "Si la Cuenta Contable tiene configurada la Tasa. Debe ser el importe total del documento y estar entre >=0 y <=99999999999.99",
        "AL": "Si la Cuenta Contable tiene configurada la Tasa. Debe ser el importe total del documento y estar entre >=0 y <=99999999999.99",
        "AM": "Especificar solo si Tipo Conversión es 'F'. Se permite 'M' Compra y 'V' Venta.",
        "AN": "Especificar solo para comprobantes de compras con IGV sin derecho de crédito Fiscal. Se detalle solo en la cuenta 42xxxx",
        "AO": "Obligatorio para comprobantes de compras, valores validos 0,10,18.",
    },
    "row3": {
        "A": "Tamaño/Formato", "B": "4 Caracteres", "C": "6 Caracteres", "D": "dd/mm/aaaa", "E": "2 Caracteres",
        "F": "40 Caracteres", "G": "Numérico 11, 6", "H": "1 Caracteres", "I": "1 Caracteres", "J": "dd/mm/aaaa",
        "K": "12 Caracteres", "L": "18 Caracteres", "M": "6 Caracteres", "N": "1 Carácter", "O": "Numérico 14,2",
        "P": "Numérico 14,2", "Q": "Numérico 14,2", "R": "2 Caracteres", "S": "20 Caracteres", "T": "dd/mm/aaaa",
        "U": "dd/mm/aaaa", "V": "3 Caracteres", "W": "30 Caracteres", "X": "18 Caracteres", "Y": "8 Caracteres",
        "Z": "2 Caracteres", "AA": "20 Caracteres", "AB": "dd/mm/aaaa", "AC": "20 Caracteres", "AD": "Numérico 14,2",
        "AE": "Numérico 14,2", "AF": "'MQ'", "AG": "15 caracteres", "AH": "dd/mm/aaaa", "AI": "5 Caracteres",
        "AJ": "Numérico 14,2", "AK": "Numérico 14,2", "AL": "Numérico 14,2", "AM": "1 Caracter", "AN": "Numérico 14,2",
        "AO": "Numérico 14,2",
    },
}
COLUMNAS = list(EXCEL_HEADERS["row1"].keys())      # A … AO, 41 columnas en orden
# Formato de la plantilla oficial de CONCAR: solo estas
# 27 columnas llevan ancho propio; las demas quedan al ancho default de Excel.
ANCHOS = {
    "A": 17.29, "B": 12.71, "C": 18.71, "D": 13.71, "E": 11.71, "F": 41.43, "G": 18.71, "I": 16.71,
    "J": 14.71, "K": 15.71, "M": 16.71, "N": 12.71, "O": 18.71, "R": 17.71, "T": 16.71, "V": 15.71,
    "W": 41.14, "X": 15.71, "Y": 18.71, "Z": 14.71, "AA": 16.71, "AB": 14.71, "AC": 15.71, "AF": 19.71,
    "AI": 17.71, "AJ": 22.71, "AM": 18.71,
}
