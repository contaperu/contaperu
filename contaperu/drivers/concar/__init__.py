"""Driver CONCAR: el Excel de asientos de 41 columnas (carga masiva).

El asiento en si vive en `contaperu.asiento`, porque es contabilidad y no formato;
aqui solo queda la escritura del .xlsx y el contrato que exige `generar.py`.
"""
from ...asiento.construir import nombre
from ...asiento.datos import CONTENT_TYPE, FORMATOS, NOMBRE, OPCIONES
from .xlsx import build_xlsx, construir

__all__ = ["CONTENT_TYPE", "FORMATOS", "NOMBRE", "OPCIONES", "build_xlsx", "construir", "nombre"]
