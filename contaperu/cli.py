"""`contaperu.cli`: la línea de comandos vive desde la 1.0 en `contaperu.puertas.cli`.

El comando `contaperu` sigue siendo el mismo. Importar sus nombres desde aquí sigue funcionando con aviso hasta la
2.0, y `python -m contaperu.cli` arranca la puerta nueva.
"""
from __future__ import annotations

from ._obsoleto import reexportar

_DESTINOS = {
    "AYUDA_IMPUTACION": "contaperu.puertas.cli:AYUDA_IMPUTACION",
    "Comprobante": "contaperu.modelo:Comprobante",
    "Libro": "contaperu.modelo:Libro",
    "_consola_utf8": "contaperu.puertas.cli:_consola_utf8",
    "archivos": "contaperu.lectores.archivos",
    "asi": "contaperu.asiento",
    "cmd_comparar": "contaperu.puertas.cli:cmd_comparar",
    "cmd_configuracion": "contaperu.puertas.cli:cmd_configuracion",
    "cmd_desde_json": "contaperu.puertas.cli:cmd_desde_json",
    "cmd_diagnosticar": "contaperu.puertas.cli:cmd_diagnosticar",
    "cmd_generar": "contaperu.puertas.cli:cmd_generar",
    "comparar_sire": "contaperu.comparar_sire",
    "drivers": "contaperu.drivers",
    "gen": "contaperu._compat.generar",
    "main": "contaperu.puertas.cli:main",
    "operaciones": "contaperu._compat.operaciones",
    "serie_y_numero": "contaperu.modelo:serie_y_numero",
    "validar": "contaperu.validar",
}
_NUEVAS = {
    "gen": "contaperu.api",
    "operaciones": "contaperu.api",
}

__getattr__, __dir__ = reexportar(__name__, _DESTINOS, nuevas=_NUEVAS)


if __name__ == "__main__":
    import sys

    from contaperu.puertas.cli import main

    sys.exit(main())
