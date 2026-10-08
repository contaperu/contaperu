"""`contaperu.detracciones` se mudó a `contaperu.tributos.detracciones`.

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
    "CENTIMO": "contaperu.tributos.detracciones:CENTIMO", "Comprobante":
    "contaperu.tributos.detracciones:Comprobante", "MARCA_SIRE": "contaperu.tributos.detracciones:MARCA_SIRE",
    "NUMERO_DETRACCION_PENDIENTE": "contaperu.tributos.detracciones:NUMERO_DETRACCION_PENDIENTE", "PAGADO":
    "contaperu.tributos.detracciones:PAGADO", "PROVISIONADO": "contaperu.tributos.detracciones:PROVISIONADO",
    "ROUND_HALF_UP": "contaperu.tributos.detracciones:ROUND_HALF_UP", "TABLA_DEL_MOTOR":
    "contaperu.tributos.detracciones:TABLA_DEL_MOTOR", "a_decimal": "contaperu.tributos.detracciones:a_decimal",
    "codigos_de": "contaperu.tributos.detracciones:codigos_de", "con_el_codigo_del_contador":
    "contaperu.tributos.detracciones:con_el_codigo_del_contador", "es_comodin":
    "contaperu.tributos.detracciones:es_comodin", "esta_pendiente":
    "contaperu.tributos.detracciones:esta_pendiente", "estado_de": "contaperu.tributos.detracciones:estado_de",
    "monto_detraccion": "contaperu.tributos.detracciones:monto_detraccion", "normalizar":
    "contaperu.tributos.detracciones:normalizar", "normalizar_una":
    "contaperu.tributos.detracciones:normalizar_una", "numero_pendiente":
    "contaperu.tributos.detracciones:numero_pendiente", "tabla_de_detracciones":
    "contaperu.tributos.detracciones:tabla_de_detracciones", "tabla_del_motor":
    "contaperu.tributos.detracciones:tabla_del_motor", "tasa_de_tabla":
    "contaperu.tributos.detracciones:tasa_de_tabla", "tasa_detraccion":
    "contaperu.tributos.detracciones:tasa_detraccion", "texto_tasa":
    "contaperu.tributos.detracciones:texto_tasa",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
