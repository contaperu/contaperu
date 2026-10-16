"""Lectores: de un archivo que ya existe a comprobantes del modelo.

- `xml_ubl`  — el XML UBL 2.1 de la factura electronica de SUNAT.
- `sire_txt` — el TXT de la propuesta que SUNAT entrega en el SIRE.
- `archivos` — desarma ZIP, clasifica lo que hay dentro y ordena el resultado.

Ninguno sale a la red ni toca el disco por su cuenta: reciben bytes.
Leer PDFs o fotos NO esta aqui: eso lo hace bien un modelo de lenguaje, y este
proyecto empieza donde el dato ya esta estructurado.

**Desde la 12.11 los tres viven en `contaperu/comprobantes/`** y este paquete es su ruta de siempre. Se
mudaron porque los tres leen comprobantes y solo comprobantes: son la puerta de entrada de ese libro, no de
cualquiera —el dinero entra por `movimientos[]`, ya estructurado, y su lector de banco no existe todavia—. Lo
que entre aqui el dia que haya un lector que no sea de compras ni de ventas se vera entonces; hoy este
paquete esta congelado en la superficie publica y por eso se queda, reexportando los mismos tres nombres.
"""
from . import archivos, sire_txt, xml_ubl

__all__ = ["archivos", "sire_txt", "xml_ubl"]
