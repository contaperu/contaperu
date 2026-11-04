"""Driver `sire_no_domiciliados`: el TXT del registro de compras de no domiciliados del SIRE (el 080500).

El hermano del driver `sire`: el mismo canal y otro registro. Lo que escribe y de dónde sale cada campo está en
`txt.py`; la forma, del registro real que SUNAT aceptó en setiembre de 2026.
"""
from .txt import (BANDERAS, CAMPOS, CANAL, EXCLUYE_TIPOS, FORMATOS, LIBRO_NO_DOMICILIADOS, MOTIVOS, NOMBRE, OPCIONES,
                  OPORTUNIDAD, SinPaisDelNoDomiciliado, linea, no_caben, nombre)

__all__ = ["BANDERAS", "CAMPOS", "CANAL", "EXCLUYE_TIPOS", "FORMATOS", "LIBRO_NO_DOMICILIADOS", "MOTIVOS", "NOMBRE",
           "OPCIONES", "OPORTUNIDAD", "SinPaisDelNoDomiciliado", "linea", "no_caben", "nombre"]
