"""Driver asiento_contable: el asiento en el propio estándar, para los ERP que vienen.

Es la salida del grupo ERP (John, 15-sep-2026). Un ERP nuevo, escrito en cualquier lenguaje, no importa el Excel de un
sistema legacy: recibe el documento `open-accounting` con su bloque `asiento`, las líneas de la partida doble **sin
vocabulario legacy** —sin siglas, sin sub-diarios, sin correlativos, y sin ninguno de los dos comodines de la
detracción, ni el documento ni el número de constancia—, con el `rol` de cada línea y el código SUNAT de su documento
(`VOCABULARIO = "neutral"`, `drivers/contrato.py`). La contabilidad es la de CONCAR: las mismas cuentas, los mismos
sentidos y los mismos importes, decididos una sola vez por el núcleo (`tests/test_driver_asiento_contable.py`).

**Se llamó `asiento_neutral` hasta la 3.10**, y ese nombre decía de qué se libraba en vez de qué es: «neutral» se
eligió en la 0.7 para distinguir estas líneas de las columnas de CONCAR, de donde entonces se releían. Un ERP no busca
un asiento neutral: busca el asiento contable. El nombre viejo sigue resolviendo toda la 3.x y avisa
(`drivers.ALIAS`), y el vocabulario del contrato sigue llamándose `neutral`, que es lo que describe — las palabras del
estándar frente a las de un sistema legacy. Lo que un ERP necesita además de las líneas —qué tramo es de qué
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

NOMBRE = "asiento_contable"
# Entrega a un ERP, por el formato neutral del estándar (`drivers.contrato.CANALES`).
CANAL = "erp"
VOCABULARIO = "neutral"
FORMATOS = {"compra": "asiento_contable_json", "venta": "asiento_contable_json"}
OPCIONES = OpcionesArchivo(extension=".json")
CONTENT_TYPE = "application/json"
# Del núcleo le basta la cuenta de cada línea: el tipo va en su código SUNAT y la moneda en ISO. Exige `detraccion`
# (4.1) porque sus líneas la llevan, y un ERP que reciba este documento sin la detracción que SUNAT afirma recibiría
# un asiento incompleto sin saberlo.
EXIGE = frozenset({"detraccion"})
# Nada que configurar en su sección: lee lo general, que es contabilidad, y ningún vocabulario de un sistema.
CONFIGURACION: tuple = ()


def nombre(libro: Libro, opciones: OpcionesArchivo = OPCIONES) -> str:
    return _nombre_de_archivo(NOMBRE, libro, opciones)


def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    """Las líneas del comprobante, ya armadas y cuadradas por el núcleo → el documento `open-accounting` **completo**,
    en JSON: sus tres bloques —`libro`, `comprobantes` y `asiento`— y `_exportacion` en la raíz.

    **El bloque `comprobantes` entra en la 3.9**, y con él se acaba la carencia que tenía este archivo: un asiento
    solo, sin los comprobantes, no dice qué parte de una compra mixta era exonerada —100 gravado más 50 exonerado
    salen como una sola línea de gasto de 150, y el IGV de 18 parece calculado sobre 150—, no lleva el nombre de la
    contraparte —viajaba por accidente dentro de la glosa, solo cuando el concepto venía vacío— y no dice por qué se
    emitió una nota de crédito. Con los dos bloques el documento **se basta**, y por eso puede volver a entrar al
    motor y dar el mismo asiento, con la misma huella.

    Va SIEMPRE y no bajo una opción: un documento que solo a veces se basta obliga a quien lo lee a manejar dos
    formas, y deja condicional la única garantía que hace útil el formato.

    No escribe `imputaciones`, a propósito: el esquema exige `id_externo` en TODOS los comprobantes cuando ese bloque
    no está vacío, así que un mes cuyo productor no puso ids daría un documento que falla su propio esquema. Quien
    quiera el asiento idéntico al volver a entrar, pasa la misma imputación que la primera vez.

    **En `_exportacion`** van la huella del asiento y, por comprobante, su identidad y el tramo de líneas que le
    toca. Hasta la 3.1
    esto solo existía en la respuesta del API (`pipeline/salida.py`), así que **quien recibiera el archivo a secas
    se quedaba sin la clave con la que no repetir un comprobante** — que es justo lo que `INTEGRAR.md` le pide a
    un ERP que use. El driver tenía el índice en la mano y lo descartaba.

    No hace falta enmendar el estándar: su raíz admite cualquier clave `_` y `estandar/LEEME.md` dice que un
    productor puede llevar ahí `_exportacion`. Lo que la respuesta del API añade y el archivo no puede saber es
    `fecha` —la pone quien llama— y `archivo`, que aquí sería su propio nombre."""
    documento = {"open_accounting": OPEN_ACCOUNTING, "libro": libro.a_dict(),
                 "comprobantes": [entrada.cabecera.como_comprobante() for entrada in indice],
                 "asiento": [linea.a_dict() for linea in lineas],
                 "_exportacion": {"driver": NOMBRE, "motor": __version__,
                                  **_exportacion_de(libro, lineas, indice)}}
    return json.dumps(documento, ensure_ascii=False, indent=1).encode("utf-8"), {"lineas": len(lineas)}
