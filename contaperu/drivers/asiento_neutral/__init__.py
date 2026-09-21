"""Driver asiento_neutral: el asiento en el propio estándar, para los ERP que vienen.

Es la salida del grupo ERP (John, 15-sep-2026). Un ERP nuevo, escrito en cualquier lenguaje, no importa el Excel de un
sistema legacy: recibe el documento `open-accounting` con su bloque `asiento`, las líneas de la partida doble **sin
vocabulario legacy** —sin siglas, sin sub-diarios, sin correlativos, sin el documento comodín de la detracción—, con el
`rol` de cada línea y el código SUNAT de su documento (`VOCABULARIO = "neutral"`, `drivers/contrato.py`). La
contabilidad es la de CONCAR: las mismas cuentas, los mismos sentidos y los mismos importes, decididos una sola vez por
el núcleo (`tests/test_driver_asiento_neutral.py`). Lo que un ERP necesita además de las líneas —qué tramo es de qué
comprobante y su huella— viaja en `_exportacion.comprobantes`, y la huella del asiento en `_exportacion.huella`.

Entra de serie sin un archivo aceptado por ningún sistema, a diferencia de un driver legacy: su formato es el estándar
mismo, y lo que lo valida es su esquema (`estandar/open-accounting.schema.json`).
"""
from __future__ import annotations

import json

from ..._version import OPEN_ACCOUNTING
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
    bloque `asiento`, en JSON."""
    documento = {"open_accounting": OPEN_ACCOUNTING, "libro": libro.a_dict(),
                 "asiento": [linea.a_dict() for linea in lineas]}
    return json.dumps(documento, ensure_ascii=False, indent=1).encode("utf-8"), {"lineas": len(lineas)}
