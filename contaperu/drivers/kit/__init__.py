"""El kit de los drivers: lo que comparten para escribir un archivo, sin decidir nada de contabilidad (1.0).

- `opciones` — `Opciones`, las microdecisiones de un registro de texto, y `OpcionesArchivo`, lo mínimo que necesita un
  driver de archivo nuevo
- `texto`    — el saneado y el formato de fechas, importes y números de un registro de texto (el TXT del SIRE)
- `celdas`   — importes y fechas tal como los quiere una celda de Excel
- `xlsx`     — abrir un libro de Excel con su hoja y devolverlo en bytes
- `columnas` — un formato de columnas simples declarado como tabla, con la fuente de cada columna, y su escritor (1.1)
- `nombres`  — cómo se llama el archivo que produce un driver, una sola regla para todos (2.1)

Hasta la 0.10 esto vivía en `contaperu/formato.py`, retirado en la 2.0. Las microdecisiones son OPCIONES y no código:
así se itera con el reporte de SUNAT o del sistema en la mano sin tocar los drivers.
"""
from . import celdas, columnas, nombres, xlsx
from .nombres import nombre_de_archivo
from .opciones import Opciones, OpcionesArchivo
from .texto import armar_linea, formatear_cambio, formatear_fecha, formatear_monto, formatear_numero, negativo, sanear

__all__ = ["Opciones", "OpcionesArchivo", "armar_linea", "celdas", "columnas", "formatear_cambio", "formatear_fecha",
           "formatear_monto", "formatear_numero", "negativo", "nombre_de_archivo", "nombres", "sanear", "xlsx"]
