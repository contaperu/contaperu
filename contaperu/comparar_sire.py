"""`contaperu.comparar_sire` se mudó a `contaperu.tributos.comparar_sire`.

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
    "CAMPOS_RCE": "contaperu.tributos.comparar_sire:CAMPOS_RCE", "CAMPOS_RVIE":
    "contaperu.tributos.comparar_sire:CAMPOS_RVIE", "COMPRAS": "contaperu.tributos.comparar_sire:COMPRAS",
    "IGNORAR": "contaperu.tributos.comparar_sire:IGNORAR", "Registro":
    "contaperu.tributos.comparar_sire:Registro", "VENTAS": "contaperu.tributos.comparar_sire:VENTAS", "clave":
    "contaperu.tributos.comparar_sire:clave", "comparar": "contaperu.tributos.comparar_sire:comparar",
    "informe": "contaperu.tributos.comparar_sire:informe", "leer_bytes":
    "contaperu.tributos.comparar_sire:leer_bytes", "registro_de": "contaperu.tributos.comparar_sire:registro_de",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
