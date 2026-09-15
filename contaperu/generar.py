"""`contaperu.generar`: la generación de la 0.x, que sigue funcionando con aviso hasta la 2.0.

Desde la 1.0 el archivo de un documento se pide a `contaperu.api.exportar_archivo`, que devuelve el mismo
`Exportado`. Cada nombre de aquí resuelve a su copia con las firmas de la 0.10 (`contaperu._compat.generar`) y
avisa con `RutaObsoleta` al usarse.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "CONFIGURACION_GENERAL": "contaperu._compat.generar:CONFIGURACION_GENERAL",
    "CONFIG_POR_DEFECTO": "contaperu._compat.generar:CONFIG_POR_DEFECTO",
    "Comprobante": "contaperu._compat.generar:Comprobante",
    "ConfiguracionInvalida": "contaperu._compat.generar:ConfiguracionInvalida",
    "ErroresBloqueantes": "contaperu._compat.generar:ErroresBloqueantes",
    "Exportado": "contaperu._compat.generar:Exportado",
    "Libro": "contaperu._compat.generar:Libro",
    "Opciones": "contaperu._compat.generar:Opciones",
    "contrato": "contaperu._compat.generar:contrato",
    "drivers": "contaperu._compat.generar:drivers",
    "errores_de": "contaperu._compat.generar:errores_de",
    "etiqueta": "contaperu._compat.generar:etiqueta",
    "exigir_requisitos": "contaperu._compat.generar:exigir_requisitos",
    "fuera_de": "contaperu._compat.generar:fuera_de",
    "fundir_config": "contaperu._compat.generar:fundir_config",
    "generar": "contaperu._compat.generar:generar",
    "huella": "contaperu._compat.generar:huella",
    "lineas_de_texto": "contaperu._compat.generar:lineas_de_texto",
    "lineas_del_libro": "contaperu._compat.generar:lineas_del_libro",
    "partida_doble": "contaperu._compat.generar:partida_doble",
    "seleccionar": "contaperu._compat.generar:seleccionar",
    "serie_y_numero": "contaperu._compat.generar:serie_y_numero",
}
_NUEVAS = {
    "Comprobante": "contaperu.api.Comprobante",
    "ConfiguracionInvalida": "contaperu.api.ConfiguracionInvalida",
    "ErroresBloqueantes": "contaperu.api.ErroresBloqueantes",
    "Exportado": "contaperu.api.Exportado",
    "Libro": "contaperu.api.Libro",
    "generar": "contaperu.api.exportar_archivo",
}

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, nuevas=_NUEVAS)
