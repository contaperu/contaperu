"""La ruta de siempre del lector de XML UBL. El lector vive en `contaperu/comprobantes/xml_ubl.py`.

Desde la 12.11 los lectores están en el paquete del comprobante, porque el XML de SUNAT y la propuesta del
SIRE **solo** traen comprobantes: son la puerta de entrada de este libro y de ningún otro. Este fichero se
queda porque `contaperu.lectores.xml_ubl` está en la superficie pública congelada, y lo que está congelado no
se quita en una menor: reexporta exactamente sus quince nombres, así que quien importaba de aquí sigue
importando de aquí, sin aviso y sin cambiar una línea.

`cat` está en la lista y no sobra: es el módulo `catalogos` con su alias, y entró en la superficie el día que
se congeló. Quitarlo sería retirar un nombre público, que es cosa de una mayor.
"""
from __future__ import annotations

from ..comprobantes.xml_ubl import (NS, RAICES, RAIZ_CDR, Comprobante, ErrorContaperu, EsCdr, Libro,
                                    XmlInvalido, XmlNoSoportado, cat, es_cdr, fecha, monto, parsear,
                                    solo_digitos)

__all__ = [
    "Comprobante", "ErrorContaperu", "EsCdr", "Libro", "NS", "RAICES", "RAIZ_CDR", "XmlInvalido",
    "XmlNoSoportado", "cat", "es_cdr", "fecha", "monto", "parsear", "solo_digitos",
]
