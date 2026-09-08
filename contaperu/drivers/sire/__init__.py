"""Driver SIRE: el TXT de "reemplazar propuesta" que se sube a SUNAT.

RVIE (ventas, Anexo 3, 33 campos) y RCE (compras, Anexo 11, 37 + 4).
"""
from .txt import (EXCLUYE_TIPOS, FORMATOS, LIBRO_COMPRAS, LIBRO_VENTAS, NOMBRE,
                  OPCIONES, OPORTUNIDAD_REEMPLAZO, linea, linea_rce, linea_rvie, nombre)

__all__ = ["EXCLUYE_TIPOS", "FORMATOS", "LIBRO_COMPRAS", "LIBRO_VENTAS", "NOMBRE",
           "OPCIONES", "OPORTUNIDAD_REEMPLAZO", "linea", "linea_rce", "linea_rvie", "nombre"]
