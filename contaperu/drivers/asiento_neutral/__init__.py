"""Driver asiento_neutral: el asiento en el propio estándar, para los ERP que vienen.

Es la salida del grupo ERP (John, 15-sep-2026). Un ERP nuevo, escrito en cualquier lenguaje, no importa el Excel de un
sistema legacy: recibe el documento `open-accounting` con su bloque `asiento`, las líneas de la partida doble **sin
vocabulario legacy** —sin siglas, sin sub-diarios, sin correlativos, sin el documento comodín de la detracción—, con el
`rol` de cada línea y el código SUNAT de su documento (`VOCABULARIO = "neutral"`, `drivers/contrato.py`). La
contabilidad es la de CONCAR: las mismas cuentas, los mismos sentidos y los mismos importes, decididos una sola vez por
el núcleo (`tests/test_driver_asiento_neutral.py`). Lo que un ERP necesita además de las líneas —qué tramo es de qué
comprobante y su huella— va **dentro del archivo**, en `_exportacion`, desde la 3.1: hasta entonces esta frase decía
lo mismo pero solo era cierta llamando al API, y quien recibiera el JSON a secas se quedaba sin ello.

Entra de serie sin un archivo aceptado por ningún sistema, a diferencia de un driver legacy: su formato es el estándar
mismo, y lo que lo valida es su esquema (`estandar/open-accounting.schema.json`).
"""
from __future__ import annotations

import json

from ..._version import OPEN_ACCOUNTING, __version__
from ...asiento import exportacion_de as _exportacion_de
from ...modelo import Libro
from ..kit import OpcionesArchivo
from ..kit import nombre_de_archivo as _nombre_de_archivo

NOMBRE = "asiento_neutral"
# Un formato neutral para integrar: el grupo ERP (`drivers.contrato.GRUPOS`).
CANAL = "intercambio"
VOCABULARIO = "neutral"
FORMATOS = {"compra": "asiento_neutral_json", "venta": "asiento_neutral_json"}
OPCIONES = OpcionesArchivo(extension=".json")
CONTENT_TYPE = "application/json"
# No exige nada más que el núcleo: la cuenta de cada línea. El tipo va en su código SUNAT y la moneda en ISO.
EXIGE = frozenset()
# Nada que configurar en su sección: lee lo general, que es contabilidad, y ningún vocabulario de un sistema.
CONFIGURACION: tuple = ()


def nombre(libro: Libro, opciones: OpcionesArchivo = OPCIONES) -> str:
    return _nombre_de_archivo(NOMBRE, libro, opciones)


def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    """Las líneas neutrales, ya armadas, numeradas y cuadradas por el núcleo → el documento `open-accounting` con su
    bloque `asiento`, en JSON, **y `_exportacion` en la raíz**.

    Ahí van la huella del asiento y, por comprobante, su identidad y el tramo de líneas que le toca. Hasta la 3.1
    esto solo existía en la respuesta del API (`pipeline/salida.py`), así que **quien recibiera el archivo a secas
    se quedaba sin la clave con la que no repetir un comprobante** — que es justo lo que `INTEGRAR.md` le pide a
    un ERP que use. El driver tenía el índice en la mano y lo descartaba.

    No hace falta enmendar el estándar: su raíz admite cualquier clave `_` y `estandar/LEEME.md` dice que un
    productor puede llevar ahí `_exportacion`. Lo que la respuesta del API añade y el archivo no puede saber es
    `fecha` —la pone quien llama— y `archivo`, que aquí sería su propio nombre."""
    documento = {"open_accounting": OPEN_ACCOUNTING, "libro": libro.a_dict(),
                 "asiento": [linea.a_dict() for linea in lineas],
                 "_exportacion": {"driver": NOMBRE, "motor": __version__,
                                  **_exportacion_de(libro, lineas, indice)}}
    return json.dumps(documento, ensure_ascii=False, indent=1).encode("utf-8"), {"lineas": len(lineas)}
