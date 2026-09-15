"""Leer lo que hay dentro de un ZIP sin que un archivo pequeño se expanda hasta agotar la memoria.

Un ZIP de unos kilobytes puede declarar un contenido de gigas: es lo que se llama una bomba ZIP. Los dos lectores que
abren ZIP —`archivos.expandir` y la propuesta del SIRE dentro de su ZIP en `sire_txt`— leen cada entrada por aquí, con
tres topes:

- **por archivo descomprimido**: la propuesta del SIRE de una empresa grande pesa decenas de megas; un XML, unos kilobytes;
- **por ZIP**: la suma de lo descomprimido de un mismo ZIP;
- **de proporción**: un XML o un TXT real comprime entre 5 y 20 veces; una bomba, miles.

Se mira lo que declara la cabecera antes de leer, y `zipfile` no descomprime más de lo declarado: una cabecera que miente
sobre el tamaño falla su comprobación de CRC en vez de crecer. Los topes son del módulo para que las pruebas los rebajen
sin crear gigas en memoria.
"""
from __future__ import annotations

import zipfile

MAXIMO_POR_ARCHIVO = 64 * 1024 * 1024
MAXIMO_POR_ZIP = 128 * 1024 * 1024
PROPORCION_MAXIMA = 200

_MEGA = 1024 * 1024


class Desmedido(ValueError):
    """Una entrada del ZIP que, descomprimida, pasaría de un tope."""


def _peso(bytes_: int) -> str:
    return f"{bytes_ / _MEGA:.0f} MB" if bytes_ >= _MEGA else f"{bytes_} bytes"


def leer(z: zipfile.ZipFile, info: zipfile.ZipInfo, ya_leido: int = 0) -> bytes:
    """El contenido de `info`, o `Desmedido` si pasa de un tope. `ya_leido` es lo que ya salió descomprimido de ese ZIP."""
    if info.file_size > MAXIMO_POR_ARCHIVO:
        raise Desmedido(f"Descomprimido pesaría {_peso(info.file_size)}, y el tope por archivo es "
                        f"{_peso(MAXIMO_POR_ARCHIVO)}")
    if info.file_size > PROPORCION_MAXIMA * max(info.compress_size, 1):
        raise Desmedido(f"Se comprime {info.file_size // max(info.compress_size, 1)} veces, mucho más que un comprobante "
                        "real: no se abre, por si es un ZIP hecho para agotar la memoria")
    if ya_leido + info.file_size > MAXIMO_POR_ZIP:
        raise Desmedido(f"Con este archivo, lo descomprimido del ZIP pasaría de {_peso(MAXIMO_POR_ZIP)}")
    return z.read(info)
