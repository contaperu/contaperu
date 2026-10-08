"""`contaperu.igv` se mudó a `contaperu.tributos.igv`.

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
    "CAMPOS_NO_GRAVADO": "contaperu.tributos.igv:CAMPOS_NO_GRAVADO", "CENTIMO":
    "contaperu.tributos.igv:CENTIMO", "CERO": "contaperu.tributos.igv:CERO", "Comprobante":
    "contaperu.tributos.igv:Comprobante", "ErrorContaperu": "contaperu.tributos.igv:ErrorContaperu",
    "IgvImposible": "contaperu.tributos.igv:IgvImposible", "NoGravadoImposible":
    "contaperu.tributos.igv:NoGravadoImposible", "PRINCIPALES": "contaperu.tributos.igv:PRINCIPALES",
    "ROUND_HALF_UP": "contaperu.tributos.igv:ROUND_HALF_UP", "SIN_CREDITO_FISCAL":
    "contaperu.tributos.igv:SIN_CREDITO_FISCAL", "TOLERANCIA": "contaperu.tributos.igv:TOLERANCIA",
    "TotalImposible": "contaperu.tributos.igv:TotalImposible", "aplicar_igv":
    "contaperu.tributos.igv:aplicar_igv", "aplicar_no_gravado": "contaperu.tributos.igv:aplicar_no_gravado",
    "aplicar_total": "contaperu.tributos.igv:aplicar_total", "base_imputable":
    "contaperu.tributos.igv:base_imputable", "cat": "contaperu.tributos.igv:cat", "clase_de_igv":
    "contaperu.tributos.igv:clase_de_igv", "igv_del_asiento": "contaperu.tributos.igv:igv_del_asiento",
    "por_destino": "contaperu.tributos.igv:por_destino", "tasa_calculada":
    "contaperu.tributos.igv:tasa_calculada", "tasa_legal": "contaperu.tributos.igv:tasa_legal",
}

__all__ = sorted(_DESTINOS)

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, que="un módulo que cambió de sitio")
