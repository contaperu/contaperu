"""`contaperu.operaciones`: la fachada de la 0.x, que sigue funcionando con aviso hasta la 2.0.

Desde la 1.0 la API pública es `contaperu.api`: el documento primero, lo demás por su nombre y `driver` sin valor
por defecto. Cada nombre de aquí resuelve a su copia con las firmas de la 0.10 (`contaperu._compat.operaciones`) y
avisa con `RutaObsoleta` al usarse, no al importar el módulo.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "CLAVES_RETIRADAS": "contaperu._compat.operaciones:CLAVES_RETIRADAS",
    "CONFIGURACION_GENERAL": "contaperu._compat.operaciones:CONFIGURACION_GENERAL",
    "CONFIG_POR_DEFECTO": "contaperu._compat.operaciones:CONFIG_POR_DEFECTO",
    "CONTADOR": "contaperu._compat.operaciones:CONTADOR",
    "Comprobante": "contaperu._compat.operaciones:Comprobante",
    "ConfiguracionInvalida": "contaperu._compat.operaciones:ConfiguracionInvalida",
    "DocumentoInvalido": "contaperu._compat.operaciones:DocumentoInvalido",
    "FALTAS": "contaperu._compat.operaciones:FALTAS",
    "Libro": "contaperu._compat.operaciones:Libro",
    "MAXIMO_COMPROBANTES": "contaperu._compat.operaciones:MAXIMO_COMPROBANTES",
    "OPEN_ACCOUNTING": "contaperu._compat.operaciones:OPEN_ACCOUNTING",
    "PEDIR_A": "contaperu._compat.operaciones:PEDIR_A",
    "PROVEEDOR": "contaperu._compat.operaciones:PROVEEDOR",
    "SISTEMA": "contaperu._compat.operaciones:SISTEMA",
    "adaptar_pcge": "contaperu._compat.operaciones:adaptar_pcge",
    "asi": "contaperu._compat.operaciones:asi",
    "comprobantes_de": "contaperu._compat.operaciones:comprobantes_de",
    "con_imputacion": "contaperu._compat.operaciones:con_imputacion",
    "config_aplicada": "contaperu._compat.operaciones:config_aplicada",
    "configuracion_por_defecto": "contaperu._compat.operaciones:configuracion_por_defecto",
    "cuadrar": "contaperu._compat.operaciones:cuadrar",
    "describir_configuracion": "contaperu._compat.operaciones:describir_configuracion",
    "detracciones": "contaperu._compat.operaciones:detracciones",
    "diagnosticar": "contaperu._compat.operaciones:diagnosticar",
    "documento": "contaperu._compat.operaciones:documento",
    "drivers": "contaperu._compat.operaciones:drivers",
    "errores_de_configuracion": "contaperu._compat.operaciones:errores_de_configuracion",
    "exportar": "contaperu._compat.operaciones:exportar",
    "gen": "contaperu._compat.operaciones:gen",
    "generar_asiento": "contaperu._compat.operaciones:generar_asiento",
    "lectura_archivos": "contaperu._compat.operaciones:lectura_archivos",
    "leer_propuesta_sire": "contaperu._compat.operaciones:leer_propuesta_sire",
    "leer_xml": "contaperu._compat.operaciones:leer_xml",
    "libro_de": "contaperu._compat.operaciones:libro_de",
    "partida_doble": "contaperu._compat.operaciones:partida_doble",
    "pcge": "contaperu._compat.operaciones:pcge",
    "revisar": "contaperu._compat.operaciones:revisar",
    "serie_y_numero": "contaperu._compat.operaciones:serie_y_numero",
    "sire_txt": "contaperu._compat.operaciones:sire_txt",
    "validar": "contaperu._compat.operaciones:validar",
}
_NUEVAS = {
    "Comprobante": "contaperu.api.Comprobante",
    "ConfiguracionInvalida": "contaperu.api.ConfiguracionInvalida",
    "DocumentoInvalido": "contaperu.api.DocumentoInvalido",
    "FALTAS": "contaperu.api.FALTAS",
    "Libro": "contaperu.api.Libro",
    "MAXIMO_COMPROBANTES": "contaperu.api.MAXIMO_COMPROBANTES",
    "OPEN_ACCOUNTING": "contaperu.api.OPEN_ACCOUNTING",
    "adaptar_pcge": "contaperu.api.adaptar_pcge",
    "comprobantes_de": "contaperu.api (se prepara dentro de cada operación)",
    "con_imputacion": "contaperu.api (se prepara dentro de cada operación)",
    "config_aplicada": "contaperu.api (se prepara dentro de cada operación)",
    "configuracion_por_defecto": "contaperu.api.configuracion_por_defecto",
    "cuadrar": "contaperu.api.cuadrar",
    "describir_configuracion": "contaperu.api.describir_configuracion",
    "diagnosticar": "contaperu.api.diagnosticar",
    "documento": "contaperu.api.documento_de",
    "errores_de_configuracion": "contaperu.api.errores_de_configuracion",
    "exportar": "contaperu.api.exportar",
    "generar_asiento": "contaperu.api.generar_asiento",
    "leer_propuesta_sire": "contaperu.api.leer_propuesta_sire",
    "leer_xml": "contaperu.api.leer_xml",
    "libro_de": "contaperu.api (se prepara dentro de cada operación)",
    "revisar": "contaperu.api.revisar",
    "serie_y_numero": "contaperu.api.serie_y_numero",
}

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, nuevas=_NUEVAS)
