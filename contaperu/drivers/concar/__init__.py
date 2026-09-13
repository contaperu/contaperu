"""Driver CONCAR: el Excel de asientos de 41 columnas (carga masiva).

El asiento vive en `contaperu.asiento`, porque es contabilidad y no formato. Aquí queda lo que es de CONCAR, con el
mismo reparto que el driver de CONTASIS: sus datos (`datos.py`: columnas, cabeceras, anchos), la proyección de la
línea neutral a sus columnas (`proyeccion.py`) y la escritura del .xlsx con el punto de entrada `construir` que exige
el contrato (`xlsx.py`).
"""
from . import datos, proyeccion
from .datos import CONTENT_TYPE, EXIGE, FORMATOS, NOMBRE, OPCIONES
from .proyeccion import a_lineas, desde_fila, filas_de_comprobante, tasa_igv_entera
from .xlsx import CorrelativoDesborda, build_xlsx, construir, nombre

__all__ = ["CONTENT_TYPE", "EXIGE", "FORMATOS", "NOMBRE", "OPCIONES", "CorrelativoDesborda", "a_lineas", "build_xlsx",
           "construir", "datos", "desde_fila", "filas_de_comprobante", "nombre", "proyeccion", "tasa_igv_entera"]
