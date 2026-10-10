"""Qué significa el estado de un ticket del SIRE, y si hay que seguir sondeando.

Todo lo pesado del SIRE es asíncrono y **no hay webhooks**: la operación devuelve un `numTicket` y hay que preguntar.
El anexo documenta del 01 al 06; en producción se han observado 07, 08 y 10 que no figuran en ninguno. Lo que el
catálogo decide para esos es lo que hace esta función: **un código desconocido no es ni éxito ni fracaso**, así que
se sigue sondeando y se dice que no se reconoce. Darlo por terminado perdería el trabajo; darlo por error asustaría
sin motivo.
"""
from __future__ import annotations

import copy

from .catalogo import _CATALOGO

_ESTADOS = _CATALOGO["tickets"]["estados"]
ESTADOS_DE_TICKET: tuple[str, ...] = tuple(c for c in _ESTADOS if not c.startswith("_"))


def estado_de_ticket(codigo: str) -> dict:
    """Qué significa un `codEstadoProceso`, y qué hacer con él.

    Devuelve `{codigo, nombre, terminado, errores, descargable, conocido, seguir_sondeando}`. Los cuatro primeros
    salen del anexo; los dos últimos son la decisión, y la toma el catálogo:

    - **`conocido`** es falso para los que SUNAT no documenta y su API devuelve igual (07, 08, 10).
    - **`seguir_sondeando`** es verdadero mientras no haya terminado **y también cuando no se reconoce**. Esa segunda
      mitad es la que importa: es la que evita que un código nuevo de SUNAT se lea como un fracaso.
    """
    codigo = str(codigo or "").strip()
    estado = _ESTADOS.get(codigo) if not codigo.startswith("_") else None
    if estado is None:
        return {"codigo": codigo, "nombre": "", "terminado": False, "errores": False, "descargable": False,
                "conocido": False, "seguir_sondeando": True}
    estado = copy.deepcopy(estado)
    return {"codigo": codigo,
            "nombre": str(estado.get("nombre") or ""),
            "terminado": bool(estado.get("terminado")),
            "errores": bool(estado.get("errores")),
            "descargable": bool(estado.get("descargable")),
            "conocido": True,
            "seguir_sondeando": not bool(estado.get("terminado"))}
