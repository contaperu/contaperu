"""Lectores: de un archivo que ya existe a comprobantes del modelo.

- `xml_ubl`  — el XML UBL 2.1 de la factura electronica de SUNAT.
- `sire_txt` — el TXT de la propuesta que SUNAT entrega en el SIRE.
- `archivos` — desarma ZIP, clasifica lo que hay dentro y ordena el resultado.

Ninguno sale a la red ni toca el disco por su cuenta: reciben bytes.
Leer PDFs o fotos NO esta aqui: eso lo hace bien un modelo de lenguaje, y este
proyecto empieza donde el dato ya esta estructurado.
"""
from . import archivos, sire_txt, xml_ubl

__all__ = ["archivos", "sire_txt", "xml_ubl"]
