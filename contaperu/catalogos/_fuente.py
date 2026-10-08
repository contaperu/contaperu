"""De dónde salen los catálogos: los ficheros que viajan con el paquete, y la regla de que ninguno entra sin
su fuente.

Es la plomería que comparten los demás módulos de este paquete. Está aparte —y con nombre privado— porque lo
que tiene en común un catálogo de códigos con un mapa de columnas no es el tema, es **cómo se carga**: con
`_datos`, al importar, y reventando si falta el fichero en vez de degradar en silencio.
"""
from __future__ import annotations

from .. import _datos

CATALOGOS = _datos.leer_json("datos/sunat/catalogos.json")
if not CATALOGOS:
    raise FileNotFoundError("No encuentro los catálogos de SUNAT (datos/sunat/catalogos.json)")
# De dónde sale cada catálogo, por su nombre: ninguno entra sin fuente.
FUENTES: dict[str, str] = {nombre: tabla["fuente"] for nombre, tabla in CATALOGOS.items()}


# `tests/test_sire_campos.py` lo confronta con el lector y con el escritor, así que ahora no se
# pueden separar sin que la batería lo diga.
#
# Desde el 1-oct-2026 hay DOS mapas de este tipo —el del SIRE y el del Libro Diario 5.1 del PLE— así que la carga
# se hace una vez y no dos: lo que cambia entre ellos es el fichero, no el procedimiento.
def mapa_de_formato(ruta: str, de_quien: str) -> dict:
    """El mapa de un formato de SUNAT, columna a columna. Ninguno entra sin su fichero: si falta, el motor no
    arranca, porque un driver que escribiera columnas sin su mapa es justo lo que estos ficheros vinieron a evitar."""
    mapa = _datos.leer_json(ruta)
    if not mapa:
        raise FileNotFoundError(f"No encuentro el mapa de campos del {de_quien} ({ruta})")
    return mapa

