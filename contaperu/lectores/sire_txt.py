"""La ruta de siempre del lector de la propuesta del SIRE. El lector vive en `contaperu/comprobantes/sire_txt.py`.

Se queda por lo mismo que su hermano `xml_ubl`: `contaperu.lectores.sire_txt` está en la superficie pública
congelada y reexporta exactamente sus diecisiete nombres. Nadie cambia un import ni recibe un aviso.
"""
from __future__ import annotations

from ..comprobantes.sire_txt import (FECHAS, IGV_COMPRAS, MARCA_DETRACCION, MARCA_DETRACCION_SI, MINIMO_CAMPOS,
                                     MONTOS, ORIGEN, POS_COMPRA, POS_VENTA, Comprobante, ErrorContaperu, Libro,
                                     SireInvalido, VALOR_NO_GRAVADO, es_sire, leer_lineas, parsear)

__all__ = [
    "Comprobante", "ErrorContaperu", "FECHAS", "IGV_COMPRAS", "Libro", "MARCA_DETRACCION",
    "MARCA_DETRACCION_SI", "MINIMO_CAMPOS", "MONTOS", "ORIGEN", "POS_COMPRA", "POS_VENTA", "SireInvalido",
    "VALOR_NO_GRAVADO", "es_sire", "leer_lineas", "parsear",
]
