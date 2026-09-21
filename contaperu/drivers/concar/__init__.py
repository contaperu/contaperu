"""Driver CONCAR: el Excel de asientos de 41 columnas (carga masiva). Canal `legacy`.

El asiento vive en `contaperu.asiento`, porque es contabilidad y no formato. Aquí queda lo que es de CONCAR, con el
mismo reparto que el driver de CONTASIS: sus datos (`datos.py`: columnas, cabeceras, anchos), la proyección de la
línea neutral a sus columnas (`proyeccion.py`) y la escritura del .xlsx con el punto de entrada `desde_lineas` que exige
el contrato (`xlsx.py`). Hasta la 0.10 la forma era `construir`, retirada en la 2.0: el archivo se pide a
`contaperu.api.exportar_archivo`.
"""
from . import datos, proyeccion
from .datos import CANAL, COLUMNAS_ELEGIBLES, CONFIGURACION, CONTENT_TYPE, EXIGE, FORMATOS, NOMBRE, OPCIONES
from .proyeccion import a_lineas, desde_fila, filas_de_comprobante, tasa_igv_entera
from .xlsx import CorrelativoDesborda, desde_lineas, escribir_xlsx, nombre

__all__ = ["CANAL", "COLUMNAS_ELEGIBLES", "CONFIGURACION", "CONTENT_TYPE", "EXIGE", "FORMATOS", "NOMBRE", "OPCIONES",
           "CorrelativoDesborda", "a_lineas", "datos", "desde_fila", "desde_lineas", "escribir_xlsx",
           "filas_de_comprobante", "nombre", "proyeccion", "tasa_igv_entera"]
