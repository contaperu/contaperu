"""La configuración contable por defecto: lo que vale para cualquier entorno hasta que su configuración diga otra cosa.

Lleva contabilidad general —cuentas por defecto, centros de costo, detracciones— y las claves que un sistema contable
de destino necesita que se configuren por entorno: la sigla de cada tipo de comprobante (`tipos.NN.sigla`), los
sub-diarios y el código de moneda de CONCAR, y el medio de pago de CONTASIS. Los datos de FORMATO de cada
destino —columnas, cabeceras, anchos— no están aquí: viven en su driver (`drivers/concar/datos.py`,
`drivers/contasis/datos.py`).

Aquí no hay lógica: si cambia un valor por defecto, se toca este archivo y nada más. Hasta el 12-sep-2026 era
`asiento/datos.py` y llevaba también los datos del Excel de CONCAR.
"""
from __future__ import annotations

from typing import Any

from ..configuracion import Campo

# La línea de la detracción, calcada del Excel real que CONCAR ACEPTÓ (set-2026): tipo de documento
# **DR** y el comodín del número —la constancia del depósito no se conoce al provisionar, se paga
# días después—. El `DT` que hubo hasta entonces salía del borrador de la plantilla y nunca llegó a
# importarse en un CONCAR de verdad; el archivo validado dice DR. Es la sigla de la Tabla General 06,
# que cada contribuyente numera a su gusto: por eso `detraccion_tipo_doc` puede cambiarla.
TIPO_DOC_DETRACCION = "DR"
NUMERO_DETRACCION_PENDIENTE = "9999999999"

# ── Valores por defecto (manual de asientos de referencia; sobreescribibles por RUC) ──
# `cuentas.gasto` va VACÍO a propósito: en la práctica es el comodín "63/65", que no es
# una cuenta. Aquí la pone la imputación o la configuración del entorno (`config_contable.cuentas.gasto`).
CONFIG_POR_DEFECTO: dict[str, Any] = {
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
        # Las cuentas de los otros tributos y del ICBPER, que el registro de CONTASIS lleva cuando su columna trae
        # importe. Vacías a propósito: son cuentas de cada empresa, y sin ellas la columna sale en blanco.
        "otros_tributos": "",
        "icbper": "",
    },
    # Código SUNAT (Tabla 10) → {sigla (en CONCAR, su columna R y su T.G. 06), sub-diario}. Los habituales:
    # 11 compras, 13 boletas, 15 honorarios (y 10 para la factura con detracción, ver abajo). Los
    # demás tipos de la Tabla 10 NO están a propósito: cada CONCAR tiene su T.G. 06 → por RUC.
    # Desde el 29-ago-2026 los sub-diarios se gobiernan POR USO (sub_diario_compras /
    # _ventas / _detraccion y los dos tipos con registro propio): un tipo solo lleva
    # `sub_diario` aquí cuando su registro ES otro (boletas, honorarios). Un
    # `tipos.NN.sub_diario` puesto por el estudio en su jsonb sigue ganando al general.
    "tipos": {
        "01": {"sigla": "FT"},                       # Factura
        "02": {"sigla": "RH", "sub_diario": "15"},   # Recibo por honorarios
        "03": {"sigla": "BV", "sub_diario": "13"},   # Boleta de venta
        "05": {"sigla": "BA"},                       # Boleto aéreo
        "07": {"sigla": "NC"},                       # Nota de crédito
        "08": {"sigla": "ND"},                       # Nota de débito
        "12": {"sigla": "TK"},                       # Ticket
        "14": {"sigla": "RC"},                       # Recibo de servicios públicos (regla de contabilidad)
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
    "centro_en_anexo_del_tercero": True,
    # Y en las cuentas que NO lo llevan en M, el centro puede ir a la X de SU PROPIA línea, como
    # referencia: «algunas empresas optan en colocar la columna X como referencia el centro de
    # costo» (el contador, 09-sep-2026). Apagado de fábrica, y por dos motivos: es una opción y no
    # la norma, y la propia plantilla de CONCAR avisa de que X solo se llena «si Cuenta Contable
    # tiene seleccionado Tipo de Anexo Referencia» — escribirla donde no toca puede hacer que
    # rechace la importación. Es INDEPENDIENTE de `centro_en_anexo_del_tercero`, que es la X del tercero.
    "centro_como_referencia": False,
    # El medio de pago de las VENTAS en el registro de CONTASIS (la tabla del comentario de su plantilla): 001 «depósito
    # en cuenta», el de todas las filas del registro que CONTASIS importó. Es del entorno, no de cada documento.
    "medio_pago": "001",
}


# ── Lo que el núcleo lee al armar un asiento: cada driver de asientos lo incluye en su sección ─────────────────────
# Llena campos de la línea neutral (la sigla del documento, el sub-diario, la línea y el código de la detracción),
# así que no es de un sistema en particular: CONCAR y el CSV lo declaran igual, y cada uno lo guarda en su sección.

_SUB_DIARIO = r"^([0-9]{1,4})?$"       # de 1 a 4 dígitos, como texto: los ceros de la izquierda cuentan ("05")

CONFIGURACION_DEL_ASIENTO: tuple[Campo, ...] = (
    # Código SUNAT (Tabla 10) → {sigla (en CONCAR, su columna R y su T.G. 06), sub-diario}. Los habituales: 11 compras,
    # 13 boletas, 15 honorarios. Los demás tipos de la Tabla 10 NO están a propósito: cada sistema tiene su tabla de
    # documentos, así que van por empresa. Un tipo solo lleva `sub_diario` cuando su registro ES otro (boletas,
    # honorarios); si no, manda el sub-diario por uso (abajo).
    Campo("tipos", "mapa", {"01": {"sigla": "FT"}, "02": {"sigla": "RH", "sub_diario": "15"},
                            "03": {"sigla": "BV", "sub_diario": "13"}, "05": {"sigla": "BA"}, "07": {"sigla": "NC"},
                            "08": {"sigla": "ND"}, "12": {"sigla": "TK"}, "14": {"sigla": "RC"}},
          titulo="Tipos de comprobante", grupo="tipos", claves=r"^[0-9]{2}$",
          ayuda="La sigla con la que tu sistema llama a cada tipo de SUNAT. Un tipo sin sigla detiene la exportación.",
          valores=Campo("", "objeto", grupo="tipos", campos=(
              Campo("sigla", "texto", titulo="Sigla", grupo="tipos"),
              Campo("sub_diario", "texto", titulo="Sub-diario propio", grupo="tipos", patron=_SUB_DIARIO)))),
    # Los sub-diarios se gobiernan POR USO (29-ago-2026): ventas → detracción → registro propio del tipo → compras.
    Campo("sub_diario_ventas", "texto", "05", titulo="Registro de Ventas", grupo="subdiarios", patron=_SUB_DIARIO,
          ayuda="Todas las ventas salen a este sub-diario."),
    Campo("sub_diario_compras", "texto", "11", titulo="Registro de Compras", grupo="subdiarios", patron=_SUB_DIARIO,
          ayuda="Facturas, tickets, notas y todo lo que no tiene registro propio."),
    # '' = la factura con detracción se queda en el sub-diario de su tipo.
    Campo("sub_diario_detraccion", "texto", "10", titulo="Compras con detracción", grupo="subdiarios",
          patron=_SUB_DIARIO, ayuda="La factura afecta a detracción sale aparte. ¿Tu sistema no las separa? Pon el "
                                    "mismo número que en compras."),
    Campo("detraccion_tipo_doc", "texto", TIPO_DOC_DETRACCION, titulo="Tipo de documento de la detracción",
          grupo="detracciones", patron=r"^[A-Z0-9]{1,2}$",
          ayuda="La sigla con la que tu sistema reconoce la línea de la detracción, como DR."),
    # Código SUNAT del bien o servicio (3 dígitos, viene en el XML) → código interno de la T.G. 28 de CONCAR (5 dígitos:
    # el de SUNAT + 2 propios). Un código que no esté aquí sale como SUNAT + "01" (el patrón más común).
    # QUÉ ENTRA (los más usados, no todos): todo el Anexo 3 —los servicios, que son lo que un estudio ve a diario— más
    # el transporte de bienes por vía terrestre (027) y las tres de bienes que aparecen en obra y comercio (madera,
    # arena y piedra, residuos). Los siete que ya usaba un contribuyente real conservan su código interno EXACTO.
    Campo("detraccion_codigos", "mapa", {"008": "00801", "009": "00901", "010": "01001", "012": "01201",
                                         "019": "01903", "020": "02001", "021": "02101", "022": "02201",
                                         "024": "02401", "025": "02501", "026": "02601", "027": "02702",
                                         "030": "03001", "037": "03701"},
          titulo="Código de cada detracción en tu sistema", grupo="detracciones", claves=r"^[0-9]{3}$",
          ayuda="El código interno de tu sistema para cada código SUNAT.",
          valores=Campo("", "texto", grupo="detracciones", patron=r"^[0-9]{2,12}$")),
)
