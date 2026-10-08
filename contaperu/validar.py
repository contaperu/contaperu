"""`contaperu.validar` se mudó a `contaperu.tributos.validar`.

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
    "Comprobante": "contaperu.tributos.validar:Comprobante", "Libro": "contaperu.tributos.validar:Libro",
    "PLAZO_ANOTACION_MESES": "contaperu.tributos.validar:PLAZO_ANOTACION_MESES", "TOLERANCIA":
    "contaperu.tributos.validar:TOLERANCIA", "avisar_de_facturas_con_nota":
    "contaperu.tributos.validar:avisar_de_facturas_con_nota", "cat": "contaperu.tributos.validar:cat",
    "fijar_estado": "contaperu.tributos.validar:fijar_estado", "marcar_duplicados":
    "contaperu.tributos.validar:marcar_duplicados", "revisar": "contaperu.tributos.validar:revisar",
    "solo_digitos": "contaperu.tributos.validar:solo_digitos", "validar": "contaperu.tributos.validar:validar",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
