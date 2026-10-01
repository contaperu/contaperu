"""Lo que el núcleo lee al armar un asiento: la sigla y el sub-diario de cada tipo de comprobante y los sub-diarios por
uso (`CONFIGURACION_DEL_ASIENTO`).

No es de un sistema en particular: llena campos de la línea del comprobante, así que cada driver de asientos lo incluye en su
sección —CONCAR y el CSV— y cada uno lo guarda en la suya. Lo general de la contabilidad (cuentas, centros de costo,
tasas de detracción) se declara en `contaperu/configuracion.py`, y lo propio de cada sistema, en su driver.

Aquí no hay lógica: si cambia un valor por defecto, se toca este archivo y nada más. Hasta el 13-sep-2026 aquí vivía
`CONFIG_POR_DEFECTO`, una sola configuración plana con todo junto; hasta el 12-sep-2026 el módulo era
`asiento/datos.py` y llevaba también los datos del Excel de CONCAR.

**Y hasta la 3.10 vivían aquí también la sigla `DR` y el mapa de códigos internos de la detracción**, que el núcleo
leía y escribía en la línea para todos los destinos. No eran del asiento: son dos Tablas Generales de CONCAR —la 06 y
la 28—, y se las llevaban igual el CSV y STARSOFT, que trabajan con el código de SUNAT. Desde la 4.0 se declaran en
`drivers/concar/datos.py`, junto a la tercera (el área de la T.G. 26), y el núcleo ya no las lee: la línea lleva el
código del Catálogo 54 y cada driver traduce al vocabulario de su sistema.
"""
from __future__ import annotations

from ..configuracion import NUMERO_DETRACCION_PENDIENTE as _NUMERO_DETRACCION_PENDIENTE, Campo

# El comodín del número vive con su campo, en `contaperu/configuracion.py`: desde la 3.1 se configura
# (`detraccion_numero_pendiente`) y su campo es GENERAL, no del asiento, porque ese número sale también
# en las columnas de constancia de un registro. Se reexporta aquí, que es donde se lee desde siempre.
NUMERO_DETRACCION_PENDIENTE = _NUMERO_DETRACCION_PENDIENTE

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
)
