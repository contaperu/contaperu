"""Lo que el núcleo lee al armar un asiento: la sigla y el sub-diario de cada tipo de comprobante, los sub-diarios por
uso y la línea de la detracción (`CONFIGURACION_DEL_ASIENTO`).

No es de un sistema en particular: llena campos de la línea neutral, así que cada driver de asientos lo incluye en su
sección —CONCAR y el CSV— y cada uno lo guarda en la suya. Lo general de la contabilidad (cuentas, centros de costo,
tasas de detracción) se declara en `contaperu/configuracion.py`, y lo propio de cada sistema, en su driver.

Aquí no hay lógica: si cambia un valor por defecto, se toca este archivo y nada más. Hasta el 13-sep-2026 aquí vivía
`CONFIG_POR_DEFECTO`, una sola configuración plana con todo junto; hasta el 12-sep-2026 el módulo era
`asiento/datos.py` y llevaba también los datos del Excel de CONCAR.
"""
from __future__ import annotations

from ..configuracion import Campo

# La línea de la detracción, calcada del Excel real que CONCAR ACEPTÓ (set-2026): tipo de documento
# **DR** y el comodín del número —la constancia del depósito no se conoce al provisionar, se paga
# días después—. El `DT` que hubo hasta entonces salía del borrador de la plantilla y nunca llegó a
# importarse en un CONCAR de verdad; el archivo validado dice DR. Es la sigla de la Tabla General 06,
# que cada contribuyente numera a su gusto: por eso `detraccion_tipo_doc` puede cambiarla.
TIPO_DOC_DETRACCION = "DR"
# NUEVE nueves, contados por John (22-sep-2026). Hasta la 2.5 eran diez, y cambiarlo mueve el asiento de CONCAR,
# no solo el de STARSOFT: es el número del documento comodín de la línea `DR`, y también lo que sale como número de
# constancia en los destinos que tienen esa columna mientras nadie haya pegado la de verdad.
#
# ⚠️ DEUDA: el TIPO del documento se configura (`detraccion_tipo_doc`, abajo) y el NÚMERO no. La asimetría es de
# cuando el comodín era un detalle de CONCAR; hoy lo ven tres destinos y tarde o temprano alguno querrá el suyo.
NUMERO_DETRACCION_PENDIENTE = "999999999"

# La clave donde un sistema de asientos dice el código de cada moneda en su vocabulario ({"PEN": "MN", "USD": "US"}). Es
# la única clave de la sección de un sistema que lee el núcleo —para saber qué monedas tienen código
# (`asiento.monedas_sin_codigo`)—, y solo cuenta para un driver que exige `moneda` y la declara (CONCAR); lo comprueba
# `drivers.contrato.incumplimientos`.
MONEDAS_CODIGO = "monedas_codigo"

_SUB_DIARIO = r"^([0-9]{1,4})?$"       # de 1 a 4 dígitos, como texto: los ceros de la izquierda cuentan ("05")

CONFIGURACION_DEL_ASIENTO: tuple[Campo, ...] = (
    # Código SUNAT (Tabla 10) → {sigla (en CONCAR, su columna R y su T.G. 06), sub-diario}. Los habituales: 11 compras,
    # 13 boletas, 15 honorarios (y 10 para la factura con detracción, abajo). Los demás tipos de la Tabla 10 NO están
    # a propósito: cada sistema tiene su tabla de documentos, así que van por empresa. Un tipo solo lleva `sub_diario`
    # cuando su registro ES otro (boletas, honorarios); el que pone la empresa gana al sub-diario por uso.
    Campo("tipos", "mapa", {"01": {"sigla": "FT"}, "02": {"sigla": "RH", "sub_diario": "15"},
                            "03": {"sigla": "BV", "sub_diario": "13"}, "05": {"sigla": "BA"}, "07": {"sigla": "NC"},
                            "08": {"sigla": "ND"}, "12": {"sigla": "TK"}, "14": {"sigla": "RC"}},
          titulo="Tipos de comprobante", grupo="tipos", claves=r"^[0-9]{2}$",
          ayuda="La sigla con la que TU sistema llama a cada tipo de SUNAT. Vienen rellenas para que no empieces "
                "de cero, pero son de cada instalación —tu sistema contable deja cambiarlas—: compáralas una vez "
                "con las tuyas antes de exportar el primer mes. Una sigla equivocada no da error: el archivo "
                "entra y el comprobante queda registrado como otra cosa. Un tipo sin sigla sí detiene la "
                "exportación.",
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
    # arena y piedra, residuos). Fuera quedan las sectoriales (pesca, oro, minerales…): la que aparezca se añade. Los
    # siete que ya usaba un contribuyente real conservan su código interno EXACTO.
    Campo("detraccion_codigos", "mapa", {"008": "00801", "009": "00901", "010": "01001", "012": "01201",
                                         "019": "01903", "020": "02001", "021": "02101", "022": "02201",
                                         "024": "02401", "025": "02501", "026": "02601", "027": "02702",
                                         "030": "03001", "037": "03701"},
          titulo="Código de cada detracción en tu sistema", grupo="detracciones", claves=r"^[0-9]{3}$",
          ayuda="El código interno de tu sistema para cada código SUNAT.",
          valores=Campo("", "texto", grupo="detracciones", patron=r"^[0-9]{2,12}$")),
)
