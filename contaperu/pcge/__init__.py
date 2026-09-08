"""Adaptacion al Plan Contable General Empresarial 2026.

La tabla de equivalencias (`pcge2026.json`) esta VACIA a proposito: ninguna regla
contable entra en este repositorio sin la cita de la norma que la respalda. Ver
`adaptar.py` para el formato y el porque.
"""
from .adaptar import Informe, Mapeo, TablaInvalida, adaptar, cargar

__all__ = ["Informe", "Mapeo", "TablaInvalida", "adaptar", "cargar"]
