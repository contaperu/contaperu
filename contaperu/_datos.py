"""Los datos que viajan dentro del paquete, y el único módulo del motor que lee bytes de un archivo.

El núcleo no toca el disco (hito 0.5 de la hoja de ruta): recibe bytes o diccionarios. Lo que el propio paquete trae
consigo —el catálogo del PCGE, la tabla de equivalencias, el esquema del estándar, el contrato OpenConta— se lee aquí,
con `importlib.resources`, que funciona igual instalado, desde una rueda o desde el repositorio. `tests/test_capas.py`
vigila que ningún otro módulo del núcleo ni de los drivers abra un archivo.

`leer_archivo` existe solo para las rutas de la 0.x que recibían la ruta de un archivo (`comparar_sire.leer`,
`pcge.cargar_equivalencias(ruta)`): siguen funcionando con aviso, y leen por aquí.
"""
from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any

PAQUETE = "contaperu"
ESQUEMA = "estandar/open-accounting.schema.json"


def leer_bytes(ruta: str) -> bytes | None:
    """Los bytes de un dato empaquetado (`"pcge/catalogo2026.json"`), o None si no viaja en esta instalación."""
    recurso = resources.files(PAQUETE).joinpath(*ruta.split("/"))
    return recurso.read_bytes() if recurso.is_file() else None


def leer_json(ruta: str) -> Any:
    """Un dato empaquetado en JSON, o None si no viaja en esta instalación."""
    datos = leer_bytes(ruta)
    return None if datos is None else json.loads(datos.decode("utf-8"))


def texto_del_esquema() -> str:
    """El esquema del estándar `open-accounting`, tal cual. Instalado viaja dentro del paquete (`contaperu/estandar/`,
    por el `force-include` de `pyproject.toml`); en el repositorio vive una sola vez, en `estandar/` de la raíz."""
    datos = leer_bytes(ESQUEMA)
    if datos is None:
        en_la_raiz = Path(__file__).resolve().parent.parent / ESQUEMA
        if not en_la_raiz.is_file():
            raise FileNotFoundError("No encuentro open-accounting.schema.json")
        datos = en_la_raiz.read_bytes()
    return datos.decode("utf-8")


def esquema_open_accounting() -> dict:
    return json.loads(texto_del_esquema())


def leer_archivo(ruta: str | os.PathLike) -> bytes | None:
    """Los bytes de un archivo que nombró quien llama, o None si no existe. Solo para las rutas de la 0.x."""
    ruta = Path(ruta)
    return ruta.read_bytes() if ruta.is_file() else None
