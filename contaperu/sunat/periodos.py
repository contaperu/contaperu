"""Qué dice SUNAT del estado de un periodo: si su registro ya se generó, o sea, si hay algo DECLARADO que bajar.

La pregunta tiene un porqué práctico: **la propuesta del SIRE no es lo declarado**. Es el borrador de SUNAT, sigue viva
y se actualiza a diario aunque el mes ya esté generado —en un RUC real, la de setiembre de 2026 traía 3 040
comprobantes y lo generado, 1 326—. Quien quiera enseñar lo que se declaró tiene que saber antes si el mes se generó,
y eso lo contesta `periodos` (Compras v28 5.33) con un `codEstado` por mes.

El manual no dice los códigos. Los del catálogo (`estados_de_periodo` en `datos/sunat/sire_api.json`) se **midieron**
contra producción el 01-nov-2026, y de ahí sale también la decisión para los que no están: **un código desconocido
cuenta como NO presentado**. Es lo contrario de lo que hace `estado_de_ticket` con los suyos, y por el mismo motivo
—elegir el error que no hace daño—: un ticket desconocido se sigue sondeando para no perder el trabajo, y un periodo
desconocido se sigue trabajando con la propuesta, que es lo que se hacía antes de poder preguntar, en vez de pedir un
registro que quizá no existe.
"""
from __future__ import annotations

import copy

from .catalogo import _CATALOGO

_ESTADOS = _CATALOGO["estados_de_periodo"]["estados"]
ESTADOS_DE_PERIODO: tuple[str, ...] = tuple(c for c in _ESTADOS if not c.startswith("_"))


def estado_de_periodo(codigo: str) -> dict:
    """Qué significa el `codEstado` de un mes en la respuesta de `periodos`.

    Devuelve `{codigo, nombre, presentado, conocido}`. **`presentado`** es la respuesta a «¿se generó el registro?»
    —el 01 y el 02 lo son, los dos con el nombre «Presentado»; el 03 no—, y **`conocido`** es falso para un código
    que el catálogo no tiene, que entonces cuenta como no presentado.
    """
    codigo = str(codigo or "").strip()
    estado = _ESTADOS.get(codigo) if not codigo.startswith("_") else None
    if estado is None:
        return {"codigo": codigo, "nombre": "", "presentado": False, "conocido": False}
    estado = copy.deepcopy(estado)
    return {"codigo": codigo,
            "nombre": str(estado.get("nombre") or ""),
            "presentado": bool(estado.get("presentado")),
            "conocido": True}
