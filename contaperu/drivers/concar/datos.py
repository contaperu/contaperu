"""Los DATOS del driver CONCAR: su identidad en el contrato, la cabecera literal del Excel oficial (41 columnas,
verificada celda a celda contra `plantilla-concar.xlsx` el 23-ago-2026), la hoja y los anchos.

Aquí no hay lógica: si CONCAR cambia una columna, se toca este archivo y nada más. Hasta el 12-sep-2026 vivía en
`asiento/datos.py`, dentro del núcleo; salió a su driver con el mismo reparto que CONTASIS.
"""
from __future__ import annotations

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from ...configuracion import Campo, Columna
from ..kit import Opciones

NOMBRE = "concar"
# Un sistema contable instalado que importa un archivo (`drivers.contrato.CANALES`).
CANAL = "legacy"
# El `fecha` no lo lee nadie al escribir: una celda de Excel lleva una fecha de verdad y el formato lo pone
# `number_format` (`xlsx.py`). Queda declarado porque es cómo se ve la columna en CONCAR.
OPCIONES = Opciones(fecha="DD/MM/AAAA", extension=".xlsx")
FORMATOS = {"compra": "concar_xlsx", "venta": "concar_xlsx"}
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Lo que CONCAR no puede importar sin (contrato de driver, `EXIGE`): el centro de costo en las cuentas
# que lo llevan en la columna M —el contador, 06-sep-2026: obligatorio donde de verdad se escribe— y
# una moneda con código en su Tabla General 03 (solo MN y US). Desde el 11-sep-2026 lo hace cumplir el
# propio driver; hasta entonces solo lo avisaba `diagnosticar` y lo negaba el portal por su cuenta.
EXIGE = frozenset({"centro_costo", "moneda"})

# Con qué cuentas nace una empresa que lleva CONCAR. **Solo la del gasto**, y eso dice algo que hasta hoy no estaba
# escrito en ninguna parte: las demás cuentas de lo general (`configuracion.CONFIGURACION_GENERAL`) —421201, 401111,
# 121201, 701101, 424101, 401721, 421203— YA SON LAS DE CONCAR, el PCGE a seis dígitos. Repetirlas aquí sería el
# mismo dato en dos sitios sin nadie que los compare, y el día que lo general mejorara, CONCAR se quedaría atrás.
# Se declara lo que se aparta, que es la regla del contrato (`drivers/contrato.py`).
#
# `631101` la eligió John (22-sep-2026) como la cuenta con la que arranca una empresa suya. **Ponerla tiene una
# consecuencia que conviene tener presente**: con una cuenta de gasto por defecto, el motor deja de contar como
# `sin_cuenta` los comprobantes a los que nadie les puso una, así que un mes con compras sin cuenta sale «listo
# para exportar» y esas filas se imputan aquí. Es lo que venía haciendo por su cuenta la aplicación que ya sembraba
# un comodín, y quien integre el motor y prefiera que le avisen lo consigue poniendo `cuentas.gasto` en blanco en
# su configuración: lo que la empresa guarda manda sobre esto.
CUENTAS_POR_DEFECTO: dict = {"gasto": "631101"}

# Lo que se configura en la sección `concar`: lo que el núcleo lee al armar el asiento, y lo propio de este formato.
CONFIGURACION = (
    *CONFIGURACION_DEL_ASIENTO,
    # Columna E, el código de la T.G. 03. CONCAR solo admite MN y US (rechaza ME): otra moneda detiene la exportación.
    Campo("monedas_codigo", "objeto", titulo="Monedas", grupo="monedas", campos=(
        Campo("PEN", "texto", "MN", titulo="Los soles se llaman", grupo="monedas",
              ayuda="Cómo escribe tu sistema la moneda nacional."),
        Campo("USD", "texto", "US", titulo="Los dólares se llaman", grupo="monedas",
              ayuda="Ojo: CONCAR usa US, no ME."))),
    # Columna V de la línea de la detracción: el área de la T.G. 26. VACÍA a propósito: es un número propio de cada
    # empresa, y uno de fábrica metería los apuntes de todo el mundo en un área que nadie eligió. No se corta a los 3
    # caracteres de la plantilla: un código cortado es OTRA área.
    Campo("detraccion_area", "texto", "", titulo="Área de la detracción", grupo="detracciones",
          patron=r"^[A-Z0-9]{0,3}$", ayuda="El código de área de tu CONCAR para la línea de la detracción (por "
                                            "ejemplo 061). Vacío, no se escribe."),
)

TIPO_CONVERSION = "V"       # CONCAR busca el T.C. en su tabla; con T.C. en G pasa a 'C' (especial)
MARCA_CONVERSION = "S"      # la columna I, «Flag de Conversión de Moneda»
COLUMNAS_IMPORTE = ("O", "P", "Q", "AD", "AE", "AK", "AL")
COLUMNAS_FECHA = ("D", "J", "T", "U", "AB", "AH")
COLUMNAS_TEXTO = ("B", "C", "E", "F", "H", "I", "K", "L", "M", "N", "R", "S", "V", "W", "X", "Y", "Z", "AA", "AI")

# La hoja de la plantilla oficial: su nombre, el panel congelado bajo las tres filas de cabecera y el autofiltro sobre
# la fila de formatos.
HOJA = "CONCAR"
PANEL = "A4"
AUTOFILTRO = "A3:AO3"

# ── Encabezados de la plantilla oficial (literal; verificado contra plantilla-concar.xlsx) ──
CABECERAS: dict[str, dict[str, str]] = {
    "titulos": {
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
    "notas": {
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
    "formatos": {
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
COLUMNAS = list(CABECERAS["titulos"].keys())      # A … AO, 41 columnas en orden
# Formato de la plantilla oficial de CONCAR: solo estas
# 27 columnas llevan ancho propio; las demas quedan al ancho default de Excel.
ANCHOS = {
    "A": 17.29, "B": 12.71, "C": 18.71, "D": 13.71, "E": 11.71, "F": 41.43, "G": 18.71, "I": 16.71,
    "J": 14.71, "K": 15.71, "M": 16.71, "N": 12.71, "O": 18.71, "R": 17.71, "T": 16.71, "V": 15.71,
    "W": 41.14, "X": 15.71, "Y": 18.71, "Z": 14.71, "AA": 16.71, "AB": 14.71, "AC": 15.71, "AF": 19.71,
    "AI": 17.71, "AJ": 22.71, "AM": 18.71,
}

# En qué columnas puede ir el centro de costo (John, 13-sep-2026: el dato se guarda una vez y la sección de cada sistema
# elige dónde sale). Cada una dice qué campo de qué línea neutral la llena: la M, el centro de la línea del gasto o del
# ingreso; la X, su anexo auxiliar.
COLUMNAS_ELEGIBLES = {"centro_costo": (
    # La principal, siempre: la M de la línea cuya cuenta lleva centro (`cuentas_con_centro`).
    Columna("centro_costo", "Código de Centro de Costo", {"compra": "M", "venta": "M"}, fija=True,
            ayuda="En la línea del gasto o del ingreso, cuando su cuenta lleva centro de costo.",
            rol="principal", campo="centro_costo"),
    # «Algunas empresas optan en colocar la columna X como referencia el centro de costo» (el contador, 09-sep-2026).
    # Sin marcar: la plantilla avisa de que X solo se llena «si Cuenta Contable tiene seleccionado Tipo de Anexo
    # Referencia», y escribirla donde no toca puede hacer que CONCAR rechace la importación. Nunca va en M y X a la vez.
    Columna("anexo_auxiliar", "Código de Anexo Auxiliar", {"compra": "X", "venta": "X"},
            ayuda="En la línea del gasto o del ingreso cuya cuenta NO lleva centro, como referencia. Solo si esa "
                  "cuenta tiene anexo referencia en tu CONCAR.",
            rol="principal", campo="anexo_auxiliar"),
    # El «doble anexo»: el centro también en la línea del proveedor o del cliente, como en el Excel que CONCAR aceptó.
    Columna("anexo_auxiliar_del_tercero", "Código de Anexo Auxiliar", {"compra": "X", "venta": "X"}, marcada=True,
            ayuda="En la línea del proveedor o del cliente. Nunca en un recibo por honorarios, ni cuando la base se "
                  "reparte entre centros distintos.",
            rol="tercero", campo="anexo_auxiliar"),
)}
