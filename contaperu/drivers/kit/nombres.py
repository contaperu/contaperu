"""Cómo se llama el archivo que produce un driver (2.1).

Una sola regla, escrita una vez: **`SISTEMA_LIBRO_PERIODO_RUC` + la extensión del driver**. El sistema delante y el
RUC al final es lo que pidió John el 21-sep-2026, y sale de cómo se busca un archivo cuando se llevan 30-80
contribuyentes: por sistema y por mes, no por número de RUC.

Hasta la 2.0 cada driver repetía su propia `f-string` y convivían tres convenciones —`CONCAR_<RUC>_<PERIODO>_COMPRAS`,
`asiento_<RUC>_<PERIODO>_compra` en minúscula y singular, y la del SIRE—. El día que entra un driver nuevo, su nombre
sale de aquí y no hay nada que decidir.

**El SIRE es la única excepción y no pasa por aquí** (`drivers/sire/txt.py`): su nombre lo impone SUNAT.
"""
from __future__ import annotations

from ...modelo import Libro
from .opciones import Opciones, OpcionesArchivo


def nombre_de_archivo(sistema: str, libro: Libro, opciones: Opciones | OpcionesArchivo) -> str:
    """`SISTEMA_LIBRO_PERIODO_RUC` + la extensión: `STARSOFT_COMPRAS_202507_20601234567.csv`.

    `sistema` es el `NOMBRE` del driver, que se pone en mayúscula. La extensión sale de sus opciones y **nunca se
    omite**: el ZIP del SIRE se arma cortando por el último punto (`pipeline/salida.py`), y un nombre sin extensión
    dejaría el TXT de dentro sin la suya.
    """
    return (f"{sistema.upper()}_{'VENTAS' if libro.es_venta else 'COMPRAS'}"
            f"_{libro.periodo}_{libro.ruc}{opciones.extension}")
