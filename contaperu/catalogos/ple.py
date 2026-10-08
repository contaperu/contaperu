"""El formato del PLE: el Libro Diario 5.1 y el detalle del plan contable 5.3, columna a columna.

Hermano de `sire`, con una diferencia que manda en todo: el del SIRE se LEE y este se ESCRIBE. Donde aquel
dice `lectura` y `vuelve`, este dice `escritura` y `visto`.
"""
from __future__ import annotations

from ._fuente import mapa_de_formato

_CAMPOS_PLE = mapa_de_formato("datos/sunat/ple_campos.json", "PLE")
# El único formato del PLE que el motor escribe hoy. No es `libro.tipo`: el driver toma un mes de compras o de
# ventas y lo escribe como Libro Diario, igual que el `sire` lo escribe como RVIE o RCE.
FORMATO_PLE = "diario"


def campos_del_ple() -> dict:
    """El formato del Libro Diario 5.1 del PLE columna a columna, con sus fuentes: por cada uno de los 21 campos, su
    número, su nombre, de dónde lo saca el driver al escribirlo —o por qué va vacío— y qué hizo con esa columna un
    libro real que SUNAT aceptó.

    Trae además los códigos de libro del PLE y la nomenclatura del fichero. **El motor no LEE un 5.1**: no hay
    lector, así que este mapa describe la escritura y nada más."""
    return dict(_CAMPOS_PLE)


def columnas_del_ple(formato: str = FORMATO_PLE) -> list[dict]:
    """Las 21 columnas del formato, en el orden que manda SUNAT."""
    return list(_CAMPOS_PLE["libros"][formato]["campos"])

