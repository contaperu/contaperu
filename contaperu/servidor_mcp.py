"""`contaperu.servidor_mcp`: el servidor MCP vive desde la 1.0 en `contaperu.puertas.servidor_mcp`.

El comando `contaperu-mcp`, las herramientas y los recursos siguen siendo los mismos. Importar sus nombres desde
aquí sigue funcionando con aviso hasta la 2.0, y `python -m contaperu.servidor_mcp` arranca la puerta nueva.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "DocumentoInvalido": "contaperu.errores:DocumentoInvalido",
    "INSTRUCCIONES": "contaperu.puertas.servidor_mcp:INSTRUCCIONES",
    "LOCALES": "contaperu.puertas.servidor_mcp:LOCALES",
    "MAXIMO_ARCHIVO": "contaperu.puertas.servidor_mcp:MAXIMO_ARCHIVO",
    "adaptar_pcge2026": "contaperu.puertas.servidor_mcp:adaptar_pcge2026",
    "buscar_cuenta_pcge": "contaperu.puertas.servidor_mcp:buscar_cuenta_pcge",
    "catalogo_pcge2026": "contaperu.puertas.servidor_mcp:catalogo_pcge2026",
    "catalogos": "contaperu.catalogos",
    "catalogos_sunat": "contaperu.puertas.servidor_mcp:catalogos_sunat",
    "catalogos_del_estandar": "contaperu.puertas.servidor_mcp:catalogos_del_estandar",
    "configuracion_declarada": "contaperu.puertas.servidor_mcp:configuracion_declarada",
    "configuracion_por_defecto": "contaperu.puertas.servidor_mcp:configuracion_por_defecto",
    "detracciones": "contaperu.detracciones",
    "diagnosticar": "contaperu.puertas.servidor_mcp:diagnosticar",
    "drivers": "contaperu.drivers",
    "drivers_disponibles": "contaperu.puertas.servidor_mcp:drivers_disponibles",
    "esquema_open_accounting": "contaperu.puertas.servidor_mcp:esquema_open_accounting",
    "exportar": "contaperu.puertas.servidor_mcp:exportar",
    "generar_asiento": "contaperu.puertas.servidor_mcp:generar_asiento",
    "leer_propuesta_sire": "contaperu.puertas.servidor_mcp:leer_propuesta_sire",
    "leer_xml_ubl": "contaperu.puertas.servidor_mcp:leer_xml_ubl",
    "main": "contaperu.puertas.servidor_mcp:main",
    "mcp": "contaperu.puertas.servidor_mcp:mcp",
    "normalizar_detracciones": "contaperu.puertas.servidor_mcp:normalizar_detracciones",
    "operaciones": "contaperu._compat.operaciones",
    "pcge": "contaperu.pcge",
    "seguridad": "contaperu.puertas.servidor_mcp:seguridad",
    "validar_comprobantes": "contaperu.puertas.servidor_mcp:validar_comprobantes",
    "validar_partida_doble": "contaperu.puertas.servidor_mcp:validar_partida_doble",
}
_NUEVAS = {
    "DocumentoInvalido": "contaperu.api.DocumentoInvalido",
    "operaciones": "contaperu.api",
}

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, nuevas=_NUEVAS)


if __name__ == "__main__":
    import sys

    from contaperu.puertas.servidor_mcp import main

    sys.exit(main())
