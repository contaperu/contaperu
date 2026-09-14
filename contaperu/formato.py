"""`contaperu.formato`: las piezas comunes de los drivers viven desde la 1.0 en `contaperu.drivers.kit`.

Cada nombre de aquí sigue resolviendo hasta la 2.0 y avisa con `RutaObsoleta` al usarse. `columnas_igv_compras` es del
TXT del SIRE y vive en su driver.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "Comprobante": "contaperu.modelo:Comprobante",
    "Opciones": "contaperu.drivers.kit:Opciones",
    "armar_linea": "contaperu.drivers.kit:armar_linea",
    "columnas_igv_compras": "contaperu.drivers.sire.txt:columnas_igv_compras",
    "formatear_cambio": "contaperu.drivers.kit:formatear_cambio",
    "formatear_fecha": "contaperu.drivers.kit:formatear_fecha",
    "formatear_monto": "contaperu.drivers.kit:formatear_monto",
    "formatear_numero": "contaperu.drivers.kit:formatear_numero",
    "negativo": "contaperu.drivers.kit:negativo",
    "por_destino": "contaperu.igv:por_destino",
    "sanear": "contaperu.drivers.kit:sanear",
}

__getattr__, __dir__ = reexportar(__name__, _DESTINOS)
