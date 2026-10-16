"""La ruta de siempre de la lectura de archivos. Vive en `contaperu/comprobantes/archivos.py`.

Se queda por lo mismo que sus hermanos: `contaperu.lectores.archivos` está en la superficie pública congelada
y reexporta exactamente sus dieciocho nombres. Dos de ellos —`sire_txt` y `xml_ubl`— son módulos, y son los de
`comprobantes`: quien hacía `archivos.xml_ubl.parsear(...)` llega al mismo sitio de siempre.
"""
from __future__ import annotations

from ..comprobantes.archivos import (EXT_AUXILIAR, EXT_IMAGEN, EXT_PDF, EXT_TEXTO, EXT_XML, EXT_ZIP,
                                     Comprobante, Entrada, Libro, Lote, ResultadoLectura, TOPE_ARCHIVOS,
                                     clave_orden, convertir_xml, expandir, ordenar, sire_txt, xml_ubl)

__all__ = [
    "Comprobante", "EXT_AUXILIAR", "EXT_IMAGEN", "EXT_PDF", "EXT_TEXTO", "EXT_XML", "EXT_ZIP", "Entrada",
    "Libro", "Lote", "ResultadoLectura", "TOPE_ARCHIVOS", "clave_orden", "convertir_xml", "expandir",
    "ordenar", "sire_txt", "xml_ubl",
]
