"""Driver `ple`: el Libro Diario, formato 5.1, del Programa de Libros Electrónicos de SUNAT.

El segundo libro electrónico del motor, junto al del SIRE, y el primero cuya fila es una **línea del asiento**. Lo
que escribe y de dónde sale cada campo está en `txt.py` y en `datos/sunat/ple_campos.json`.
"""
from .txt import (BANDERAS, CAMPOS, CANAL, CONFIGURACION, CONTENT_TYPE, FORMATOS, LIBRO_DIARIO, NOMBRE, OPCIONES, OPORTUNIDAD,
                  desde_lineas, fila, nombre)

__all__ = ["BANDERAS", "CAMPOS", "CANAL", "CONFIGURACION", "CONTENT_TYPE", "FORMATOS", "LIBRO_DIARIO", "NOMBRE", "OPCIONES",
           "OPORTUNIDAD", "desde_lineas", "fila", "nombre"]
