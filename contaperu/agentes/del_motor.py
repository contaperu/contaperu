"""El catálogo de las herramientas del motor, derivado de la tabla de operaciones y no escrito otra vez.

Son las operaciones de `api.OPERACIONES` que declaran `herramienta`, una por herramienta y en el orden de la tabla: el
servidor público las publica granulares, que es lo que ya ven sus usuarios. Todas miran y ninguna sale a la red —el
motor no guarda nada ni llama a nadie—, así que todas tienen el mismo riesgo. Su título, su grupo y su perfil son los
de la tabla y `api.textos`.
"""
from __future__ import annotations

from typing import Iterable

from .. import api
from ..api import textos
from .catalogo import MIRA, Catalogo, Ficha

__all__ = ["DEL_MOTOR", "catalogo_del_motor"]


def catalogo_del_motor(operaciones: Iterable[api.Operacion] | None = None) -> Catalogo:
    """El catálogo de las operaciones del motor que son herramientas: las de `api.OPERACIONES` si no se dan otras. Lo
    usan las fábricas en cada llamada, así que un servidor ve la tabla de ese momento."""
    return Catalogo(Ficha(op.nombre, op.herramienta, titulo=textos.TITULOS[op.herramienta], riesgo=MIRA,
                          grupo=op.grupo, perfil=op.perfil)
                    for op in (api.OPERACIONES if operaciones is None else operaciones) if op.herramienta)


DEL_MOTOR = catalogo_del_motor()
