"""La escritura del archivo y el punto de entrada que exige el contrato (`desde_lineas`).

**Escribe un CSV, y es deliberado mientras no haya plantilla oficial.** STARSOFT importa un Excel —«carga de
archivo Excel», vídeo de ventas 19:08—, pero de su plantilla no consta lo que hace falta para escribirla sin
adivinar: el nombre de la hoja, en qué fila empieza el cuerpo, si hay cabeceras que respetar, el formato real de
las fechas y las longitudes de cada columna. Cinco de sus columnas (`A`-`E`) ni siquiera se leyeron: se dedujeron
de la narración.

Un `.xlsx` escrito con esas cinco incógnitas produce un archivo que STARSOFT rechaza entero o, peor, acepta mal.
Un CSV con las mismas filas se abre, se revisa columna por columna con un contador y dice exactamente lo que el
driver sabe hoy. El día que llegue la plantilla, cambia este módulo y la proyección no se toca.

Este archivo se llamará `xlsx.py`, como en CONCAR y CONTASIS, cuando escriba lo que su nombre diría.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from ...asiento.indice import ComprobanteDelAsiento
from ...asiento.lineas import LineaDiario
from ...modelo import Libro
from ..kit import OpcionesArchivo, nombre_de_archivo
from . import datos, proyeccion
from .datos import OPCIONES

SEPARADOR = ";"          # el de un Excel en español, que es donde se va a abrir
BOM = "﻿"           # para que Excel reconozca el UTF-8 sin preguntar


def nombre(libro: Libro, opciones: OpcionesArchivo = OPCIONES) -> str:
    return nombre_de_archivo(datos.NOMBRE, libro, opciones)


def escribir(libro: Libro, filas: list[dict[str, Any]]) -> bytes:
    """Las filas proyectadas, en el orden de las columnas de su libro."""
    cabeceras = [cabecera for _, cabecera, _ in datos.COLUMNAS[libro.tipo]]
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=cabeceras, delimiter=SEPARADOR,
                              lineterminator="\r\n", extrasaction="ignore")
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({c: ("" if fila.get(c) is None else fila.get(c, "")) for c in cabeceras})
    return (BOM + buffer.getvalue()).encode("utf-8")


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict,
                 opciones: OpcionesArchivo = OPCIONES, *,
                 indice: tuple[ComprobanteDelAsiento, ...] = ()) -> tuple[bytes, dict]:
    """Las líneas neutrales del libro, ya numeradas y cuadradas por el núcleo → el archivo y lo que STARSOFT suma
    al resumen.

    Necesita el `indice`: cada fila lleva datos de la CABECERA de su comprobante —el IGV del total, el número sin
    partir y el destino de la adquisición— que ninguna línea guarda.
    """
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    if lineas and not indice:
        raise ValueError("STARSOFT escribe cada fila con la cabecera de su comprobante: necesita el `indice` "
                         "del asiento")
    # STARSOFT no mira el reloj y el motor tampoco: la fecha de registro es la de cada comprobante, no la de hoy.
    filas: list[dict[str, Any]] = []
    for entrada in indice:
        filas.extend(proyeccion.filas(entrada.cabecera, entrada.lineas(lineas), libro, config,
                                      entrada.cabecera.fecha_emision))
    # `sub_diarios` NO se pone aquí: lo calcula el núcleo con sus rangos (`asiento.numerar_en_orden`) y lo
    # que devuelva el driver lo PISA (`pipeline/armado.py`). Hasta la 2.0 esto devolvía la lista de
    # sub-diarios presentes y borraba el diccionario de rangos, que es lo que un ERP guarda para proponer
    # el correlativo del mes siguiente: quien lo consumiera esperando un dict se encontraba una lista.
    resumen = {"filas": len(filas)}
    return escribir(libro, filas), resumen


# Se reexporta para que `desde_lineas` compruebe el libro sin importar el módulo entero.
FORMATOS = datos.FORMATOS
