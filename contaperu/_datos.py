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
# Los archivos del estándar viven UNA vez, en `estandar/` de la raíz del repositorio, y viajan dentro del paquete por
# el `force-include` de `pyproject.toml` (`contaperu/estandar/`). Que estén en dos sitios según de dónde se corra lo
# sabe solo `del_estandar`, para no repetir esa doble búsqueda en cada archivo nuevo.
ESTANDAR = "estandar"
ESQUEMA = f"{ESTANDAR}/open-accounting.schema.json"
CATALOGOS_DEL_ESTANDAR = f"{ESTANDAR}/catalogos.json"


def leer_bytes(ruta: str) -> bytes | None:
    """Los bytes de un dato empaquetado (`"pcge/catalogo2026.json"`), o None si no viaja en esta instalación."""
    recurso = resources.files(PAQUETE).joinpath(*ruta.split("/"))
    return recurso.read_bytes() if recurso.is_file() else None


def leer_json(ruta: str) -> Any:
    """Un dato empaquetado en JSON, o None si no viaja en esta instalación."""
    datos = leer_bytes(ruta)
    return None if datos is None else json.loads(datos.decode("utf-8"))


def del_estandar(ruta: str) -> bytes:
    """Los bytes de un archivo del estándar. Instalado viaja dentro del paquete (`contaperu/estandar/`, por el
    `force-include` de `pyproject.toml`); en el repositorio vive una sola vez, en `estandar/` de la raíz. Un archivo
    nuevo en `estandar/` necesita su línea de `force-include` y nada más."""
    datos = leer_bytes(ruta)
    if datos is None:
        en_la_raiz = Path(__file__).resolve().parent.parent / ruta
        if not en_la_raiz.is_file():
            raise FileNotFoundError(f"No encuentro {ruta}")
        datos = en_la_raiz.read_bytes()
    return datos


def texto_del_esquema() -> str:
    """El esquema del estándar `open-accounting`, tal cual."""
    return del_estandar(ESQUEMA).decode("utf-8")


def catalogos_del_estandar() -> Any:
    """Los catálogos que este estándar inventa: `roles`, `clases` y `tipos_de_libro`."""
    return json.loads(del_estandar(CATALOGOS_DEL_ESTANDAR).decode("utf-8"))


def esquema_open_accounting() -> dict:
    return json.loads(texto_del_esquema())


def leer_esquema(nombre: str) -> dict:
    """Un esquema de la api (`contaperu/api/esquemas/<nombre>.schema.json`)."""
    datos = leer_json(f"api/esquemas/{nombre}.schema.json")
    if datos is None:
        raise FileNotFoundError(f"No encuentro el esquema {nombre!r} de la api")
    return datos


def openconta() -> dict:
    """El contrato OpenConta que viaja con esta versión (`contaperu/api/openconta.json`)."""
    datos = leer_json("api/openconta.json")
    if datos is None:
        raise FileNotFoundError("No encuentro contaperu/api/openconta.json")
    return datos


def leer_archivo(ruta: str | os.PathLike) -> bytes | None:
    """Los bytes de un archivo que nombró quien llama, o None si no existe. Solo para las rutas de la 0.x."""
    ruta = Path(ruta)
    return ruta.read_bytes() if ruta.is_file() else None
