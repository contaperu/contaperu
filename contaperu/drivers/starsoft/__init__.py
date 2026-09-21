"""Driver STARSOFT: la plantilla de importación de asientos. Canal `legacy`.

STARSOFT importa asientos, no un registro: en su plantilla cada fila es una cuenta, con su debe o haber y su
importe, y las filas de un comprobante comparten cabecera. Por eso este driver es `desde_lineas`, como CONCAR, y
no `desde_comprobantes`, como CONTASIS. El asiento lo arma el núcleo; aquí solo se traduce.

**Lo que lo hace distinto de CONCAR**, con el mismo documento delante:

- el sub-diario de compras es `4` y el de ventas `03`, no `11` y `05`;
- el voucher va sin el mes que CONCAR lleva delante: `0001` y no `070001`;
- el número del documento va pegado y con ceros (`F13600000431`), al revés que en CONCAR y el SIRE;
- la nota de crédito se llama **`CC`** y no `NC` —`FT` y `BV` sí coinciden—;
- y lleva una columna que CONCAR no tiene: **`DESTINO`**, el destino del IGV de la adquisición, porque su
  plantilla mezcla el asiento con el registro tributario en la misma fila.

Esa última columna es la que hizo falta ampliar la cabecera del índice en la 1.4.0: el dato existía en el
estándar (`destino_igv`) y no llegaba a un driver de asientos.

**Estado: EN PRUEBAS.** El formato se levantó el 20-sep-2026 de dos vídeos y sus capturas
(`STARSOFT-INTEGRACION.md`), no de una plantilla oficial. Lo que no consta está marcado `[por confirmar]` en el
código, y la mitad de la tabla de siglas está vacía a propósito: un tipo sin equivalente detiene la exportación
en vez de inventarse uno. **Nadie ha importado todavía en STARSOFT un archivo generado por este driver**, así
que mientras escribe un CSV revisable y no el Excel definitivo. El día que un contribuyente lo importe de
verdad, este docstring gana su línea de «Aceptado (fecha)», como la tiene CONTASIS.
"""
from __future__ import annotations

from . import datos, proyeccion
from .datos import (CANAL, COLUMNAS, COLUMNAS_ELEGIBLES, CONFIGURACION, CONTENT_TYPE, EXIGE, FORMATOS, NOMBRE,
                    OPCIONES)
from .proyeccion import destino_de, fila, filas, no_caben, numero_del_documento, voucher
from .salida import desde_lineas, escribir, nombre

__all__ = ["CANAL", "COLUMNAS", "COLUMNAS_ELEGIBLES", "CONFIGURACION", "CONTENT_TYPE", "EXIGE", "FORMATOS",
           "NOMBRE", "OPCIONES", "datos", "desde_lineas", "destino_de", "escribir", "fila", "filas", "no_caben",
           "nombre", "numero_del_documento", "proyeccion", "voucher"]
