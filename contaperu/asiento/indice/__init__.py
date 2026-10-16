"""El índice del asiento: qué líneas son de qué comprobante, con la cabecera de hechos de cada uno (1.0).

Las líneas del comprobante llevan la contabilidad y nada más, y así la huella solo cambia si cambia un asiento. Pero un sistema
contable escribe cada fila con hechos del COMPROBANTE que ninguna línea guarda: la glosa de la cabecera, la tasa del IGV
calculada desde su base y su IGV —y no desde la tasa de la línea, que ya viene redondeada—, el documento de la
contraparte, el `id_externo` con el que la aplicación lo reconoce. El índice los lleva al lado de las líneas, fuera de
ellas y fuera de la huella:

    lineas, rangos, indice = asiento.lineas_e_indice_del_libro(libro, comprobantes, config, correlativos)
    for entrada in indice:
        filas = proyectar(entrada.cabecera, entrada.lineas(lineas))

Lo recibe el driver de asientos que lo acepta (`desde_lineas(..., *, indice=())`, `drivers.contrato.acepta_indice`),
y es de donde sale lo que la respuesta dice de cada comprobante. Todo va en texto, como en el estándar: un importe es
su `Decimal` escrito, sin redondear nada.

Eran 328 líneas con tres cosas dentro, y desde la 12.12.0 cada una tiene su fichero, con el mismo corte y los mismos
tres nombres que `asiento/faltas/` y que los dos motores del asiento:

- `comprobante.py` — `Cabecera`, anclada campo a campo contra el `$defs/comprobante` del estándar,
  `ComprobanteDelAsiento` y `DETRACCION_DEL_ESTANDAR`;
- `movimiento.py` — `CabeceraDeMovimiento`, `MovimientoDelAsiento` e `identidad_de_movimiento`;
- `comun.py` — `exportacion_de` y `entradas_de`, que preguntan por `libro.rasgos.origen` y no saben de cuál de los
  dos vienen. Ésas dos son el motivo de que las dos cabeceras tengan `clave`, `identidad()` y `como_entrada()`.

**Lo que se importa no cambió**: aquí se reexportan los mismos nombres.
"""
from __future__ import annotations

from .comprobante import DETRACCION_DEL_ESTANDAR, Cabecera, ComprobanteDelAsiento
from .comun import entradas_de, exportacion_de
from .movimiento import CabeceraDeMovimiento, MovimientoDelAsiento, identidad_de_movimiento

__all__ = ["DETRACCION_DEL_ESTANDAR", "Cabecera", "ComprobanteDelAsiento",
           "CabeceraDeMovimiento", "MovimientoDelAsiento", "identidad_de_movimiento",
           "exportacion_de", "entradas_de"]
