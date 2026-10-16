"""Lo que se le pregunta a un índice sin saber de qué libro viene: con qué se reconoce su asiento después y de qué
bloque del documento salió.

Las dos funciones son el motivo por el que las dos cabeceras tienen `clave`, `identidad()` y `como_entrada()` con
esos nombres: aquí no hay un solo `if` sobre el tipo de libro. La clave del bloque la dice la tabla
(`libro.rasgos.origen`) y el contenido lo dice cada entrada, así que una compra, una venta y un movimiento pasan por
el mismo código.
"""
from __future__ import annotations

from typing import Any, Sequence

from ...modelo import Libro
from ..huella import huella
from ..lineas import LineaDiario


def exportacion_de(libro: Libro, lineas: Sequence[LineaDiario], indice: Sequence[Any]) -> dict:
    """Lo que hay que saber de un asiento para reconocerlo después: su huella y, por comprobante, su identidad, el
    tramo de líneas que le toca (`[desde, hasta)`) y la huella de ese tramo. Los tramos parten las líneas sin dejar
    hueco ni solaparse.

    Se arma aquí, y no en la capa de respuesta, porque **quien lo necesita lo tiene en la mano en dos sitios**: la
    respuesta del API lo pone en `_exportacion`, y un driver que escriba el documento del estándar puede llevarlo
    dentro del archivo, que es lo que el estándar admite en su raíz (`estandar/LEEME.md`, las claves `_`). Hasta la
    3.1 vivía solo en `pipeline/salida.py` y el archivo salía sin ello: quien recibiera el JSON a secas se quedaba
    sin la clave con la que no repetir un comprobante."""
    return {"huella": huella(lineas),
            # **La clave la dice la tabla**, y para eso `RASGOS.origen` es singular: `comprobantes` en una compra o
            # una venta, `movimientos` en tesorería. No es cosmética — quien lee la respuesta sabe qué hay dentro
            # sin mirar, y el día que entre un libro más no hay que decidirlo otra vez.
            libro.rasgos.origen: [{"identidad": entrada.identidad(libro),
                                   "lineas": [entrada.desde, entrada.hasta],
                                   "huella": huella(entrada.lineas(lineas))} for entrada in indice]}


def entradas_de(libro: Libro, indice: Sequence[Any]) -> dict:
    """El bloque del documento del que salió este asiento, bajo su propia clave: `{"comprobantes": [...]}` o
    `{"movimientos": [...]}`.

    Es lo que un driver que escriba el documento del estándar necesita para que su archivo **se baste**, y existe
    aquí por lo mismo que `exportacion_de`: la clave la dice la tabla (`RASGOS.origen`) y el contenido lo dice cada
    cabecera (`como_entrada`), así que el driver no tiene que preguntar de qué libro viene. Se devuelve un
    diccionario de una clave, y no la lista, para que se desempaquete con `**` donde se escribe el documento.
    """
    return {libro.rasgos.origen: [entrada.cabecera.como_entrada() for entrada in indice]}
