"""El catálogo de las herramientas del motor, derivado de la tabla de operaciones y no escrito otra vez.

Son las operaciones de `api.OPERACIONES` que declaran `herramienta`, una por herramienta y en el orden de la tabla: el
servidor público las publica granulares, que es lo que ya ven sus usuarios. Todas miran y ninguna sale a la red —el
motor no guarda nada ni llama a nadie—, así que todas tienen el mismo riesgo.
"""
from __future__ import annotations

from .. import api
from .catalogo import MIRA, Catalogo, Ficha

__all__ = ["DEL_MOTOR"]

DEL_MOTOR = Catalogo(Ficha(op.nombre, op.herramienta, riesgo=MIRA) for op in api.OPERACIONES if op.herramienta)
