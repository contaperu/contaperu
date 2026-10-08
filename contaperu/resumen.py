"""`contaperu.resumen` se mudó a `contaperu.contable.resumen`.

Esta ruta sigue resolviendo y avisa con `RutaObsoleta` diciendo cuál usar; desaparece en la versión que
dice `_obsoleto.RETIRO`. El aviso sale **al usar un nombre**, no al importar el módulo, para que un
`import` en el arranque de una aplicación no ensucie su registro.

`__all__` se construye del diccionario y no se escribe a mano: así `tests/test_superficie_publica` lo
encuentra —mira `__all__` antes que `vars()`, que aquí está vacío a propósito— y no hay que repetir los
nombres en dos sitios que podrían separarse.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "AGRUPACIONES": "contaperu.contable.resumen:AGRUPACIONES", "IMPORTES":
    "contaperu.contable.resumen:IMPORTES", "del_libro": "contaperu.contable.resumen:del_libro", "por_cuenta":
    "contaperu.contable.resumen:por_cuenta",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
