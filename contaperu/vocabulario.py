"""El vocabulario del estándar: los roles de una línea, las clases contables y los tipos de libro.

Los tres vivían como **enums cerrados dentro del esquema**, y dos de ellos **repetidos** en el código —`ROLES` en
`asiento/motor.py` y `TIPOS_LIBRO` en `modelo.py`— sin ningún test que comparara las copias. Desde la 1.0 viven una
sola vez, en `estandar/catalogos.json`, publicado junto al esquema y citable por la URL del tag del estándar: un ERP
de fuera lee los valores sin instalar nada, y el esquema deja de enumerarlos.

**Por qué se abren.** Con el enum dentro del esquema, el día que entre un hecho nuevo —los movimientos del banco, las
letras de cambio— sus roles costarían una versión del estándar. Con el catálogo, no cuestan ninguna: un valor nuevo se
publica con su fecha y ya (`estandar/LEEME.md`, «Versionado», los tres niveles). **Abrirlos no es que crezcan**: los
seis roles de hoy son los de compras y ventas, que son los libros que el motor genera, y no se añade ninguno hasta
que aparezca el hecho que lo necesite (John, 18-sep-2026).

**Y no degradan igual, que es lo que hay que tener claro.** Un `rol` desconocido no rompe nada: quien recibe la línea
la contabiliza con `clase`, `debe_haber` e `importe`. Un `tipo de libro` desconocido no se puede adivinar, así que su
degradación es del destino: el driver que no lo declara en sus `FORMATOS` lo rechaza limpio, diciendo qué libros lleva.

**Por qué este módulo no se llama `estandar.py`**: chocaría con el directorio `contaperu/estandar/` que el
`force-include` de `pyproject.toml` crea dentro de la rueda.
"""
from __future__ import annotations

from . import _datos

_CATALOGOS = _datos.catalogos_del_estandar()
_TABLAS = ("roles", "clases", "tipos_de_libro")

for _nombre in _TABLAS:
    if not (_CATALOGOS.get(_nombre) or {}).get("fuente"):
        raise FileNotFoundError(f"El catálogo `{_nombre}` del estándar no trae fuente (estandar/catalogos.json)")

# De dónde sale cada catálogo y en qué versión: ninguno entra sin las dos cosas.
FUENTES: dict[str, str] = {n: _CATALOGOS[n]["fuente"] for n in _TABLAS}
VERSIONES: dict[str, str] = {n: _CATALOGOS[n].get("version", "") for n in _TABLAS}

# Los valores, con su descripción, tal como se publican.
ROLES_DESCRITOS: dict[str, str] = dict(_CATALOGOS["roles"]["codigos"])
CLASES_DESCRITAS: dict[str, str] = dict(_CATALOGOS["clases"]["codigos"])
TIPOS_DE_LIBRO_DESCRITOS: dict[str, str] = dict(_CATALOGOS["tipos_de_libro"]["codigos"])

# Y las tuplas que usa el motor. Se conservan los nombres que ya estaban en la superficie pública.
ROLES: tuple[str, ...] = tuple(ROLES_DESCRITOS)
CLASES: tuple[str, ...] = tuple(CLASES_DESCRITAS)
TIPOS_LIBRO: tuple[str, ...] = tuple(TIPOS_DE_LIBRO_DESCRITOS)


def catalogos() -> dict:
    """Los tres catálogos con su fuente, su versión y sus valores, como los sirve la api."""
    return {nombre: {"fuente": _CATALOGOS[nombre]["fuente"],
                     "version": _CATALOGOS[nombre].get("version", ""),
                     "nota": _CATALOGOS[nombre].get("nota", ""),
                     "codigos": dict(_CATALOGOS[nombre]["codigos"])}
            for nombre in _TABLAS}
