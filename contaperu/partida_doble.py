"""`contaperu.partida_doble` se mudó a `contaperu.contable.partida_doble`.

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
    "CENTIMO": "contaperu.contable.partida_doble:CENTIMO", "CERO": "contaperu.contable.partida_doble:CERO",
    "Cuadre": "contaperu.contable.partida_doble:Cuadre", "Descuadre":
    "contaperu.contable.partida_doble:Descuadre", "ErrorContaperu":
    "contaperu.contable.partida_doble:ErrorContaperu", "cuadra": "contaperu.contable.partida_doble:cuadra",
    "exigir": "contaperu.contable.partida_doble:exigir",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
