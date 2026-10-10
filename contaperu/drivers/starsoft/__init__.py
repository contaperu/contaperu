"""Driver STARSOFT **Desktop**: la plantilla de importación de asientos. Canal `legacy`.

**STARSOFT son dos productos, y este driver es el de escritorio** (John, 22-sep-2026): el que importa un
archivo. El otro es **STARSOFT Web — Gold Edition**, que tiene **API pública**, y su driver se llamará
`starsoft_web` el día que alguien lo escriba. **No está en la hoja de ruta**: fue el hito A5 y se retiró el
10-oct-2026, con el motivo escrito en su §6. La puerta sigue abierta para quien quiera. Lo que aquí está resuelto le sirve casi entero —las cuentas, las siglas, los
sub-diarios, el destino del IGV y la proyección son los mismos—; lo único distinto es a dónde van los
datos: un archivo aquí, un cuerpo JSON allá.

STARSOFT importa asientos, no un registro: en su plantilla cada fila es una cuenta, con su debe o haber y su
importe, y las filas de un comprobante comparten cabecera. Por eso este driver es `desde_lineas`, como CONCAR, y
no `desde_comprobantes`, como CONTASIS. El asiento lo arma el núcleo; aquí solo se traduce.

**Lo que lo hace distinto de CONCAR**, con el mismo documento delante:

- el sub-diario de compras es `4` y el de ventas `03`, no `11` y `05`;
- el correlativo va sin el mes que CONCAR lleva delante: `0001` y no `070001`;
- el número del documento va pegado y con ceros (`F13600000431`), al revés que en CONCAR y el SIRE;
- la nota de crédito se llama **`CC`** y no `NC` —`FT` y `BV` sí coinciden—;
- y lleva una columna que CONCAR no tiene: **`DESTINO`**, el destino del IGV de la adquisición, porque su
  plantilla mezcla el asiento con el registro tributario en la misma fila.

Esa última columna es la que hizo falta ampliar la cabecera del índice en la 1.4.0: el dato existía en el
estándar (`destino_igv`) y no llegaba a un driver de asientos.

**Estado: aceptado.** STARSOFT importó un mes de compras el **7-oct-2026** y uno de ventas el **8-oct-2026**,
y cada uno destapó algo que ningún vídeo decía: el TXT va suelto, sin el ZIP, y el archivo de ventas empieza
por `V` y no por la `C` de compras, porque la letra es la del libro. Antes de eso ya había entrado uno
(22-sep-2026) que llevaba los 38 campos y las fechas al revés, y es el que obligó a cambiar de fuente.

**La fuente, y cuál manda.** El formato se levantó el 20-sep-2026 de dos vídeos del canal *ArchivoExcel* y de
las capturas de la hoja `PARAMETROS`, y se recalcó el 22 contra la documentación del fabricante —`CONT_COMPRAS`
y `CONT_VENTAS`, con la tabla de campos y ejemplos de TXT del propio sistema—. **Donde los dos hablan, manda el
manual**, y eso corrigió dos cosas de golpe: la línea lleva **35 campos en compras y 27 en ventas** (se
escribían las columnas que dependen de un «concepto general» de cada instalación, que el manual manda no
incluir) y **las dos fechas estaban cruzadas** —la del documento es la emisión y la de registro cae dentro del
periodo, que solo se nota cuando el comprobante es extemporáneo—. Los PDF no están en el repositorio porque son
de otra empresa y esto es público: su tabla de campos está volcada en `datos.CAMPOS_DEL_MANUAL`, ítem por ítem,
con la longitud y la condición de cada uno.

**La hoja `PARAMETROS`**, que sale de las capturas y no del manual, es el andamiaje de la macro de Excel y no
del motor: cuatro pares de columnas cuenta/debe-haber por tipo de asiento, cinco tipos en compras y cuatro en
ventas. **De ahí sale el límite de cuatro cuentas por asiento**, que no es del TXT —`proyeccion.no_caben`
explica por qué no se hace cumplir— y que conviene saber de dónde viene el día que alguien lo proponga.

**Lo que sigue sin constar está marcado `[por confirmar]`**, y hay cuatro marcas vivas con lo que cerraría cada
una escrito al lado. Dos son siglas, el `RH` y el `BA` heredados de CONCAR, y las cierra el maestro de tipos de
documento de una instalación (`datos.TIPOS`). Las otras dos son del destino del IGV —la precedencia entre el
004 y el 005, y el umbral del 004— y las cierra un archivo aceptado con una DUA y un destino mixto en el mismo
mes; están explicadas en `proyeccion.destino_de`, con el aviso de que son «de los errores que no dan error».
La tabla de siglas depende además de cada instalación —el manual dice «el tipo de comprobante que tiene
registrado en su sistema externo»—: un tipo sin equivalente detiene la exportación en vez de inventarse uno.

**Lo que escribe es el TXT de palotes, suelto**, que es una de las dos vías de carga de STARSOFT; la otra
es su plantilla de Excel. Hasta la 2.2 escribía un CSV, provisional, para poder revisarlo columna por
columna mientras no se conocía la plantilla; de la 2.3 a la 5.3 lo envolvió en un ZIP, hasta que un mes
real enseñó que su pantalla de importación pide el texto (John, 7-oct-2026). El nombre empieza por `C`
por la misma razón y el mismo día: `salida.nombre`.
"""
from __future__ import annotations

from . import datos, proyeccion
from .datos import (CANAL, COLUMNAS, COLUMNAS_ELEGIBLES, CONFIGURACION, CONTENT_TYPE, CUENTAS_POR_DEFECTO, EXIGE,
                    FORMATOS, NOMBRE, OPCIONES)
from .proyeccion import correlativo_de_starsoft, destino_de, fila, filas, no_caben, numero_del_documento
from .salida import desde_lineas, escribir, nombre

__all__ = ["CANAL", "COLUMNAS", "COLUMNAS_ELEGIBLES", "CONFIGURACION", "CONTENT_TYPE", "CUENTAS_POR_DEFECTO",
           "EXIGE", "FORMATOS", "NOMBRE", "OPCIONES", "correlativo_de_starsoft", "datos", "desde_lineas",
           "destino_de", "escribir", "fila",
           "filas", "no_caben", "nombre", "numero_del_documento", "proyeccion"]
