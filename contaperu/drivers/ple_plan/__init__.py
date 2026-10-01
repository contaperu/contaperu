"""Driver `ple_plan`: el detalle del plan contable utilizado (formato 5.3) del PLE de SUNAT.

El otro miembro del par del Libro Diario: el 5.1 lleva los asientos y éste, las cuentas que esos asientos usaron, con
su denominación. Lo que escribe y de dónde sale cada campo está en `txt.py` y en `datos/sunat/ple_campos.json`.
"""
from .txt import (BANDERAS, CAMPOS, CANAL, CONFIGURACION, CONTENT_TYPE, DIA_DEL_PERIODO, EXIGE, FORMATOS,
                  LIBRO_PLAN_CONTABLE, NOMBRE, OPCIONES, OPORTUNIDAD, PLAN_DE_CUENTAS, SIN_DESCRIPCION_DEL_PLAN,
                  desde_lineas, fila, nombre)

__all__ = ["BANDERAS", "CAMPOS", "CANAL", "CONFIGURACION", "CONTENT_TYPE", "DIA_DEL_PERIODO", "EXIGE", "FORMATOS",
           "LIBRO_PLAN_CONTABLE", "NOMBRE", "OPCIONES", "OPORTUNIDAD", "PLAN_DE_CUENTAS",
           "SIN_DESCRIPCION_DEL_PLAN", "desde_lineas", "fila", "nombre"]
