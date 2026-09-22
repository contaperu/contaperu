"""Driver STARSOFT **Desktop**: la plantilla de importación de asientos. Canal `legacy`.

**STARSOFT son dos productos, y este driver es el de escritorio** (John, 22-sep-2026): el que importa un
archivo. El otro es **STARSOFT Web — Gold Edition**, que tiene **API pública**, y su driver se llamará
`starsoft_web` el día que alguien lo escriba: es el hito A5 de la hoja de ruta, y la puerta está abierta
para quien quiera. Lo que aquí está resuelto le sirve casi entero —las cuentas, las siglas, los
sub-diarios, el destino del IGV y la proyección son los mismos—; lo único distinto es a dónde van los
datos: un archivo aquí, un cuerpo JSON allá.

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

**Estado: EN PRUEBAS, con la documentación oficial en la mano desde el 22-sep-2026.** El formato se
levantó el 20-sep-2026 de dos vídeos y sus capturas, y se recalcó el 22 contra la documentación de STARSOFT
—`CONT_COMPRAS` y `CONT_VENTAS`, con la tabla de campos y ejemplos de TXT del propio sistema—, que corrigió
tres cosas de golpe: **la línea lleva 35 campos en compras y 27 en ventas** (se escribían las columnas que
dependen de un «concepto general» de cada instalación, que el manual manda no incluir), y **las dos fechas
estaban cruzadas** — la del documento es la emisión y la de registro cae dentro del periodo, que solo se
nota cuando el comprobante es extemporáneo. Todo en `STARSOFT-INTEGRACION.md`; los PDF no están en el
repositorio porque son de otra empresa y esto es público.

Lo que sigue sin constar está marcado `[por confirmar]`, y la tabla de siglas depende de cada instalación
—el manual dice «el tipo de comprobante que tiene registrado en su sistema externo»—: un tipo sin
equivalente detiene la exportación en vez de inventarse uno.

**Un archivo de este driver ya entró en STARSOFT** (John, 22-sep-2026), y eso es lo que destapó las tres
correcciones de arriba. Lo que falta para la línea de «Aceptado (fecha)» que tiene CONTASIS es que entre
uno **ya corregido**: el que importó llevaba los 38 campos y las fechas al revés.

**Lo que escribe es el TXT de palotes envuelto en un ZIP** (2.3), que es una de las dos vías de carga de
STARSOFT; la otra es su plantilla de Excel. Hasta la 2.2 escribía un CSV, provisional, para poder
revisarlo columna por columna mientras no se conocía la plantilla.
"""
from __future__ import annotations

from . import datos, proyeccion
from .datos import (CANAL, COLUMNAS, COLUMNAS_ELEGIBLES, CONFIGURACION, CONTENT_TYPE, CUENTAS_POR_DEFECTO, EXIGE,
                    FORMATOS, NOMBRE, OPCIONES)
from .proyeccion import destino_de, fila, filas, no_caben, numero_del_documento, voucher
from .salida import desde_lineas, escribir, nombre

__all__ = ["CANAL", "COLUMNAS", "COLUMNAS_ELEGIBLES", "CONFIGURACION", "CONTENT_TYPE", "CUENTAS_POR_DEFECTO",
           "EXIGE", "FORMATOS", "NOMBRE", "OPCIONES", "datos", "desde_lineas", "destino_de", "escribir", "fila",
           "filas", "no_caben", "nombre", "numero_del_documento", "proyeccion", "voucher"]
